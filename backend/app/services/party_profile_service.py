from __future__ import annotations

import csv
import io
import json
import os
import re
from datetime import datetime
from typing import Any

from fastapi import UploadFile
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import local_now
from backend.app.core.errors import AppException
from backend.app.core.storage import StorageService
from backend.app.models.audit import AuditLog
from backend.app.models.user import User
from backend.app.repositories.party_repo import PartyRepository
from backend.app.services.party_notify_adapter import PartyNotifyAdapter


PARTY_TYPES = ("入党积极分子", "预备党员", "正式党员")
APPLY_STATUSES = (
    "递交申请",
    "确定为积极分子",
    "列为发展对象",
    "接受为预备党员",
    "转为正式党员",
    "停止发展",
)
ACTIVE_STATUSES = APPLY_STATUSES[:-1]
STATUS_DATE_FIELDS = {
    "递交申请": "apply_date",
    "确定为积极分子": "activist_date",
    "列为发展对象": "target_date",
    "接受为预备党员": "probation_date",
    "转为正式党员": "full_date",
}
TIMELINE_FIELDS = (
    "apply_date",
    "activist_date",
    "target_date",
    "probation_date",
    "full_date",
)
MATERIAL_TYPES = {"申请书", "思想汇报", "政审材料", "考察材料", "其他"}
MATERIAL_SCOPE = "party_materials"
ALLOWED_MATERIAL_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}
PROFILE_FIELDS = {
    "party_type",
    "branch_name",
    "class_name",
    "grade",
    *TIMELINE_FIELDS,
    "party_join_date",
    "apply_status",
    "stop_reason",
    "introducer_names",
    "mentor_names",
    "remark",
    "deleted_at",
}
MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class PartyProfileService:
    @staticmethod
    def party_classes() -> set[str]:
        raw = settings.PARTY_CLASSES
        if isinstance(raw, str):
            return {item.strip() for item in raw.split(",") if item.strip()}
        return {str(item).strip() for item in raw if str(item).strip()}

    @staticmethod
    def validate_profile(profile: dict[str, Any]) -> dict[str, Any]:
        unknown = set(profile) - PROFILE_FIELDS
        if unknown:
            raise AppException(
                "PARTY_PROFILE_INVALID",
                f"未知党员档案字段: {', '.join(sorted(unknown))}",
                422,
            )

        normalized = dict(profile)
        for key, value in list(normalized.items()):
            if isinstance(value, str):
                normalized[key] = value.strip()
        if normalized.get("party_type") not in PARTY_TYPES:
            raise AppException(
                "PARTY_PROFILE_INVALID",
                f"party_type 必须是: {', '.join(PARTY_TYPES)}",
                422,
            )
        status = normalized.get("apply_status")
        if status not in APPLY_STATUSES:
            raise AppException(
                "PARTY_PROFILE_INVALID",
                f"apply_status 必须是: {', '.join(APPLY_STATUSES)}",
                422,
            )
        class_name = normalized.get("class_name")
        if class_name not in PartyProfileService.party_classes():
            raise AppException(
                "PARTY_PROFILE_INVALID",
                f"class_name 不在运行时配置 PARTY_CLASSES 中: {class_name}",
                422,
            )
        for field in (*TIMELINE_FIELDS, "party_join_date"):
            value = normalized.get(field)
            if value and not MONTH_PATTERN.fullmatch(str(value)):
                raise AppException(
                    "PARTY_PROFILE_INVALID",
                    f"{field} 必须使用 YYYY-MM 格式",
                    422,
                )
        dated_values = [
            (field, normalized.get(field))
            for field in TIMELINE_FIELDS
            if normalized.get(field)
        ]
        for (previous_field, previous), (current_field, current) in zip(
            dated_values, dated_values[1:]
        ):
            if str(current) < str(previous):
                raise AppException(
                    "PARTY_PROFILE_INVALID",
                    f"阶段时间必须单调递增: {current_field} 不得早于 {previous_field}",
                    422,
                )

        if status == "停止发展":
            if not normalized.get("stop_reason"):
                raise AppException(
                    "PARTY_PROFILE_INVALID",
                    "apply_status 为停止发展时必须填写 stop_reason",
                    422,
                )
            if not normalized.get("apply_date"):
                raise AppException(
                    "PARTY_PROFILE_INVALID",
                    "停止发展档案仍必须保留 apply_date",
                    422,
                )
        else:
            normalized["stop_reason"] = None
            status_index = ACTIVE_STATUSES.index(status)
            for required_status in ACTIVE_STATUSES[: status_index + 1]:
                required_date = STATUS_DATE_FIELDS[required_status]
                if not normalized.get(required_date):
                    raise AppException(
                        "PARTY_PROFILE_INVALID",
                        f"apply_status 为{status}时必须填写 {required_date}",
                        422,
                    )

        party_type = normalized["party_type"]
        required_by_party_type = {
            "入党积极分子": ("apply_date",),
            "预备党员": ("apply_date", "activist_date", "target_date", "probation_date"),
            "正式党员": TIMELINE_FIELDS,
        }
        for required_date in required_by_party_type[party_type]:
            if not normalized.get(required_date):
                raise AppException(
                    "PARTY_PROFILE_INVALID",
                    f"{party_type}档案必须填写 {required_date}",
                    422,
                )
        if party_type == "正式党员" and status not in {"转为正式党员", "停止发展"}:
            raise AppException(
                "PARTY_PROFILE_INVALID",
                "正式党员的 apply_status 必须为转为正式党员或停止发展",
                422,
            )
        if party_type == "预备党员" and status not in {"接受为预备党员", "停止发展"}:
            raise AppException(
                "PARTY_PROFILE_INVALID",
                "预备党员的 apply_status 必须为接受为预备党员或停止发展",
                422,
            )
        if party_type == "入党积极分子" and status in {"接受为预备党员", "转为正式党员"}:
            raise AppException(
                "PARTY_PROFILE_INVALID",
                "入党积极分子的 apply_status 与党员类型不一致",
                422,
            )
        return normalized

    @staticmethod
    def serialize_member(user: User) -> dict[str, Any]:
        party = user.party
        return {
            "user_id": user.id,
            "student_no": user.student_no,
            "name": user.name,
            **party,
            "party": party,
        }

    @staticmethod
    def get_member_or_404(db: Session, user_id: int, *, require_profile: bool = True) -> User:
        user = PartyRepository.get_member(db, user_id)
        if not user:
            raise AppException("PARTY_MEMBER_NOT_FOUND", "学生用户不存在", 404)
        if require_profile and (not user.party.get("party_type") or user.party.get("deleted_at")):
            raise AppException("PARTY_MEMBER_NOT_FOUND", "党员档案不存在", 404)
        return user

    @staticmethod
    def create_member(db: Session, values: dict[str, Any]) -> User:
        raw_user_id = values.pop("user_id", None)
        student_no = values.pop("student_no", None)
        user = None
        if raw_user_id is not None:
            user = PartyRepository.get_member(db, int(raw_user_id))
            # Older admin forms called this field "user ID", but administrators
            # often entered a numeric student number there instead.
            if user is None:
                user = PartyRepository.get_user_by_student_no(db, str(raw_user_id))
        if user is None and student_no:
            user = PartyRepository.get_user_by_student_no(db, student_no)
        if user is None:
            if raw_user_id is None and not student_no:
                raise AppException(
                    "PARTY_MEMBER_REFERENCE_REQUIRED",
                    "必须填写学生学号或用户 ID",
                    422,
                )
            raise AppException(
                "PARTY_MEMBER_NOT_FOUND",
                "学生用户不存在，请确认学号或用户 ID",
                404,
            )
        if user.party.get("party_type") and not user.party.get("deleted_at"):
            raise AppException("PARTY_MEMBER_EXISTS", "党员档案已存在", 409)
        profile = PartyProfileService.validate_profile(values)
        profile.pop("deleted_at", None)
        PartyRepository.set_profile(db, user, profile)
        PartyProfileService._sync_political_status(db, user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def update_member(db: Session, user_id: int, values: dict[str, Any]) -> User:
        user = PartyProfileService.get_member_or_404(db, user_id)
        if "apply_status" in values and values["apply_status"] != user.party.get("apply_status"):
            raise AppException(
                "PARTY_STATUS_ENDPOINT_REQUIRED",
                "发展阶段变更必须使用状态流转接口",
                409,
            )
        profile = {**user.party, **values}
        profile.pop("deleted_at", None)
        profile = PartyProfileService.validate_profile(profile)
        PartyRepository.set_profile(db, user, profile)
        PartyProfileService._sync_political_status(db, user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def delete_member(db: Session, user_id: int) -> User:
        user = PartyProfileService.get_member_or_404(db, user_id)
        profile = dict(user.party)
        profile["deleted_at"] = local_now().isoformat()
        PartyRepository.set_profile(db, user, profile)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def change_status(
        db: Session,
        user_id: int,
        values: dict[str, Any],
        operator: User,
    ) -> User:
        user = PartyProfileService.get_member_or_404(db, user_id)
        profile = dict(user.party)
        previous = str(profile.get("apply_status") or "")
        target = str(values["apply_status"])
        if previous == "停止发展":
            raise AppException("PARTY_STATUS_CONFLICT", "已停止发展的档案不能继续流转", 409)
        if target == previous:
            raise AppException("PARTY_STATUS_CONFLICT", "目标阶段与当前阶段相同", 409)
        if target != "停止发展":
            try:
                expected = ACTIVE_STATUSES[ACTIVE_STATUSES.index(previous) + 1]
            except (ValueError, IndexError):
                expected = None
            if target != expected:
                raise AppException(
                    "PARTY_STATUS_TRANSITION_INVALID",
                    f"发展阶段只能逐级流转，当前阶段 {previous} 的下一阶段为 {expected or '无'}",
                    409,
                )
            effective_date = values.get("effective_date")
            if not effective_date:
                raise AppException(
                    "PARTY_PROFILE_INVALID",
                    "阶段流转必须提供 effective_date（YYYY-MM）",
                    422,
                )
            profile[STATUS_DATE_FIELDS[target]] = effective_date
            if target == "接受为预备党员":
                profile["party_type"] = "预备党员"
            elif target == "转为正式党员":
                profile["party_type"] = "正式党员"
                profile["party_join_date"] = profile.get("party_join_date") or effective_date
        else:
            profile["stop_reason"] = values.get("stop_reason")
        profile["apply_status"] = target
        profile = PartyProfileService.validate_profile(profile)
        PartyRepository.set_profile(db, user, profile)
        PartyProfileService._sync_political_status(db, user)
        db.add(
            AuditLog(
                operator_id=operator.id,
                operator_name=operator.name,
                action="party_status_change",
                target_type="party_member",
                target_id=str(user.id),
                result="success",
                detail=json.dumps(
                    {
                        "from": previous,
                        "to": target,
                        "effective_date": values.get("effective_date"),
                        "stop_reason": values.get("stop_reason"),
                    },
                    ensure_ascii=False,
                ),
            )
        )
        db.commit()
        db.refresh(user)
        PartyProfileService._notify_status_change(
            db, user=user, previous=previous, target=target
        )
        return user

    @staticmethod
    def _notify_status_change(db: Session, *, user: User, previous: str, target: str) -> None:
        PartyNotifyAdapter.notify_party_status_change(
            db,
            user_id=user.id,
            previous_status=previous,
            current_status=target,
        )

    @staticmethod
    def import_csv(db: Session, content: bytes) -> dict[str, Any]:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise AppException("PARTY_CSV_INVALID", "CSV 必须使用 UTF-8 编码", 422) from exc
        try:
            rows = list(csv.DictReader(io.StringIO(text)))
        except csv.Error as exc:
            raise AppException("PARTY_CSV_INVALID", f"CSV 格式错误: {exc}", 422) from exc
        if not rows:
            raise AppException("PARTY_CSV_INVALID", "CSV 没有可导入的数据", 422)
        headers = set(rows[0])
        required = {"student_no", "party_type", "class_name", "grade", "apply_date", "apply_status"}
        missing = required - headers
        if missing:
            raise AppException(
                "PARTY_CSV_INVALID",
                f"CSV 缺少列: {', '.join(sorted(missing))}",
                422,
            )

        created = updated = skipped = 0
        errors: list[dict[str, Any]] = []
        csv_fields = PROFILE_FIELDS - {"deleted_at"}
        for row_number, row in enumerate(rows, start=2):
            student_no = (row.get("student_no") or "").strip()
            try:
                with db.begin_nested():
                    if not student_no:
                        raise AppException("PARTY_PROFILE_INVALID", "student_no 不能为空", 422)
                    user = PartyRepository.get_user_by_student_no(db, student_no)
                    if not user:
                        raise AppException("PARTY_MEMBER_NOT_FOUND", "未找到对应的学生用户", 404)
                    profile = {
                        key: value.strip()
                        for key in csv_fields
                        if (value := row.get(key)) is not None and value.strip()
                    }
                    profile.setdefault("branch_name", "大数据党支部")
                    profile = PartyProfileService.validate_profile(profile)
                    existing = dict(user.party)
                    existing.pop("deleted_at", None)
                    if existing == profile:
                        skipped += 1
                        continue
                    is_new = not existing.get("party_type")
                    PartyRepository.set_profile(db, user, profile)
                    PartyProfileService._sync_political_status(db, user)
                    db.flush()
                    if is_new:
                        created += 1
                    else:
                        updated += 1
            except AppException as exc:
                errors.append(
                    {
                        "row": row_number,
                        "student_no": student_no or None,
                        "field": PartyProfileService._csv_error_field(exc.message),
                        "message": exc.message,
                    }
                )
        db.commit()
        return {
            "total": len(rows),
            "created": created,
            "added": created,
            "updated": updated,
            "skipped": skipped,
            "error_count": len(errors),
            "errors": errors,
        }

    @staticmethod
    def _csv_error_field(message: str) -> str | None:
        for field in ("student_no", *PROFILE_FIELDS):
            if field in message:
                return field
        return None

    @staticmethod
    def _sync_political_status(db: Session, user: User) -> None:
        from backend.app.services.party_political_status_service import (
            PartyPoliticalStatusService,
        )

        PartyPoliticalStatusService.sync_from_party_profile(db, user)

    @staticmethod
    def upload_material(
        db: Session,
        *,
        user_id: int,
        material_type: str,
        title: str,
        file: UploadFile,
        uploaded_by: int,
    ):
        PartyProfileService.get_member_or_404(db, user_id)
        if material_type not in MATERIAL_TYPES:
            raise AppException(
                "PARTY_MATERIAL_INVALID",
                f"material_type 必须是: {', '.join(sorted(MATERIAL_TYPES))}",
                422,
            )
        title = title.strip()
        if not title or len(title) > 200:
            raise AppException("PARTY_MATERIAL_INVALID", "材料名称长度必须为 1-200", 422)
        original_name = os.path.basename(file.filename or "")
        extension = os.path.splitext(original_name)[1].lower()
        mime_type = (file.content_type or "").lower()
        if not original_name or ALLOWED_MATERIAL_TYPES.get(extension) != mime_type:
            raise AppException(
                "PARTY_MATERIAL_INVALID",
                "党员发展材料仅支持 PDF、JPG、JPEG、PNG 格式",
                400,
            )
        if len(original_name) > 255:
            raise AppException("PARTY_MATERIAL_INVALID", "原始文件名不能超过 255 个字符", 422)
        stored_name, stored_mime, size = StorageService.save_file(
            MATERIAL_SCOPE, user_id, file
        )
        max_size = settings.PARTY_MATERIAL_MAX_MB * 1024 * 1024
        if size <= 0 or size > max_size:
            StorageService.delete_file(MATERIAL_SCOPE, user_id, stored_name)
            if size <= 0:
                message = "党员发展材料不能为空"
            else:
                message = f"单份党员发展材料不能超过 {settings.PARTY_MATERIAL_MAX_MB}MB"
            raise AppException("PARTY_MATERIAL_INVALID", message, 400)
        try:
            material = PartyRepository.create_material(
                db,
                user_id=user_id,
                material_type=material_type,
                title=title,
                original_name=original_name,
                stored_name=stored_name,
                mime_type=stored_mime,
                size=size,
                uploaded_by=uploaded_by,
            )
            db.commit()
            db.refresh(material)
            return material
        except Exception:
            db.rollback()
            StorageService.delete_file(MATERIAL_SCOPE, user_id, stored_name)
            raise

    @staticmethod
    def delete_material(db: Session, material_id: int):
        material = PartyRepository.get_material(db, material_id)
        if not material:
            raise AppException("PARTY_MATERIAL_NOT_FOUND", "党员发展材料不存在", 404)
        PartyRepository.soft_delete_material(db, material)
        db.commit()
        db.refresh(material)
        return material
