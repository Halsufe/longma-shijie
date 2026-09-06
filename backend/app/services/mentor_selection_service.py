"""Business rules for academic mentor selection."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Iterable, cast

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.database import local_now
from backend.app.core.errors import AppException
from backend.app.models.mentor_selection import (
    BatchStatus,
    DecisionStatus,
    MentorDecisionItem,
    MentorDecisionSubmission,
    MentorMatchResultItem,
    MentorMatchResultVersion,
    MentorPreferenceItem,
    MentorPreferenceSubmission,
    MentorSelectionBatch,
    MentorSelectionBatchMentor,
    MentorSelectionBatchStudent,
    PreferenceStatus,
    SelectionRound,
)
from backend.app.models.teacher import TeacherDirection
from backend.app.models.user import User


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=local_now().tzinfo) if value.tzinfo is None else value


def validate_batch_times(values: dict[str, Any]) -> None:
    required = [
        "student_apply_start", "student_apply_end", "mentor_select_start", "mentor_select_end", "main_publish_at"
    ]
    for key in required:
        if values.get(key) is None:
            raise ValueError(f"{key} 不能为空")
    starts = {key: _aware(values[key]) for key in required}
    if not starts["student_apply_start"] < starts["student_apply_end"] <= starts["mentor_select_start"] < starts["mentor_select_end"] <= starts["main_publish_at"]:
        raise ValueError("主选阶段时间必须满足 学生开始 < 学生截止 <= 导师开始 < 导师截止 <= 发布时间")
    optional = ["supplement_student_start", "supplement_student_end", "supplement_mentor_start", "supplement_mentor_end", "supplement_publish_at"]
    present = {key: values.get(key) for key in optional}
    if any(present.values()) and not all(present.values()):
        raise ValueError("补录阶段时间必须完整配置")
    if all(present.values()):
        supplement = {key: _aware(cast(datetime, present[key])) for key in optional}
        if not supplement["supplement_student_start"] >= starts["main_publish_at"]:
            raise ValueError("补录学生填报不能早于主选发布时间")
        if not supplement["supplement_student_start"] < supplement["supplement_student_end"] <= supplement["supplement_mentor_start"] < supplement["supplement_mentor_end"] <= supplement["supplement_publish_at"]:
            raise ValueError("补录阶段时间顺序无效")


class BatchStateMachine:
    transitions = {
        BatchStatus.DRAFT: {BatchStatus.STUDENT_APPLY, BatchStatus.REOPENED},
        BatchStatus.STUDENT_APPLY: {BatchStatus.MENTOR_SELECT, BatchStatus.REOPENED},
        BatchStatus.MENTOR_SELECT: {BatchStatus.MAIN_PENDING, BatchStatus.REOPENED},
        BatchStatus.MAIN_PENDING: {BatchStatus.MAIN_PUBLISHED, BatchStatus.REOPENED},
        BatchStatus.MAIN_PUBLISHED: {BatchStatus.SUPPLEMENT_STUDENT_APPLY, BatchStatus.COMPLETED, BatchStatus.REOPENED},
        BatchStatus.SUPPLEMENT_STUDENT_APPLY: {BatchStatus.SUPPLEMENT_MENTOR_SELECT, BatchStatus.REOPENED},
        BatchStatus.SUPPLEMENT_MENTOR_SELECT: {BatchStatus.SUPPLEMENT_PENDING, BatchStatus.REOPENED},
        BatchStatus.SUPPLEMENT_PENDING: {BatchStatus.SUPPLEMENT_PUBLISHED, BatchStatus.SUPPLEMENT_BLOCKED, BatchStatus.REOPENED},
        BatchStatus.SUPPLEMENT_BLOCKED: {BatchStatus.SUPPLEMENT_STUDENT_APPLY, BatchStatus.SUPPLEMENT_MENTOR_SELECT, BatchStatus.REOPENED},
        BatchStatus.SUPPLEMENT_PUBLISHED: {BatchStatus.COMPLETED, BatchStatus.REOPENED},
        BatchStatus.REOPENED: {BatchStatus.STUDENT_APPLY, BatchStatus.MENTOR_SELECT},
        BatchStatus.COMPLETED: set(),
    }

    @classmethod
    def move(cls, batch: MentorSelectionBatch, target: str) -> None:
        if target not in cls.transitions.get(batch.status, set()):
            raise AppException("MENTOR_SELECTION_INVALID_TRANSITION", f"不能从 {batch.status} 进入 {target}", 409)
        batch.status = target
        batch.active_key = None if target == BatchStatus.COMPLETED else "mentor_selection_active"


def _active_batch(db: Session) -> MentorSelectionBatch | None:
    return db.query(MentorSelectionBatch).filter(
        MentorSelectionBatch.active_key == "mentor_selection_active",
        MentorSelectionBatch.deleted_at.is_(None),
    ).first()


class BatchService:
    @staticmethod
    def create(db: Session, data: dict[str, Any], created_by: int) -> MentorSelectionBatch:
        try:
            validate_batch_times(data)
        except ValueError as exc:
            raise AppException("MENTOR_SELECTION_INVALID_TIME", str(exc), 400) from exc
        if _active_batch(db):
            raise AppException("MENTOR_SELECTION_ACTIVE_EXISTS", "已有进行中的双选批次", 409)
        batch = MentorSelectionBatch(
            **data,
            created_by=created_by,
            active_key="mentor_selection_active",
        )
        db.add(batch)
        db.flush()
        db.commit()
        db.refresh(batch)
        return batch

    @staticmethod
    def update(db: Session, batch: MentorSelectionBatch, data: dict[str, Any]) -> MentorSelectionBatch:
        expected = data.pop("expected_version", None)
        if expected is not None and expected != batch.version_no:
            raise AppException("MENTOR_SELECTION_VERSION_CONFLICT", "批次已被其他操作更新，请刷新后重试", 409)
        values = {key: getattr(batch, key) for key in (
            "student_apply_start", "student_apply_end", "mentor_select_start", "mentor_select_end", "main_publish_at",
            "supplement_student_start", "supplement_student_end", "supplement_mentor_start", "supplement_mentor_end", "supplement_publish_at"
        )}
        values.update({key: value for key, value in data.items() if key in values})
        try:
            validate_batch_times(values)
        except ValueError as exc:
            raise AppException("MENTOR_SELECTION_INVALID_TIME", str(exc), 400) from exc
        if batch.status != BatchStatus.DRAFT and any(key in data for key in values):
            raise AppException("MENTOR_SELECTION_STAGE_LOCKED", "批次开始后不能修改阶段时间", 409)
        for key, value in data.items():
            if hasattr(batch, key) and key not in {"status", "active_key", "version_no", "expected_version"}:
                setattr(batch, key, value)
        batch.version_no += 1
        db.commit()
        db.refresh(batch)
        return batch

    @staticmethod
    def extend(db: Session, batch: MentorSelectionBatch, stage: str, new_end: datetime) -> MentorSelectionBatch:
        if _aware(new_end) <= local_now():
            raise AppException("MENTOR_SELECTION_INVALID_TIME", "新的截止时间必须晚于当前时间", 400)
        field = {
            "student": "student_apply_end", "mentor": "mentor_select_end",
            "supplement_student": "supplement_student_end", "supplement_mentor": "supplement_mentor_end",
        }[stage]
        old = getattr(batch, field)
        if old is not None and _aware(new_end) <= _aware(old):
            raise AppException("MENTOR_SELECTION_INVALID_TIME", "只能延长阶段，不能缩短阶段", 400)
        setattr(batch, field, new_end)
        if batch.status == BatchStatus.SUPPLEMENT_BLOCKED:
            batch.status = (
                BatchStatus.SUPPLEMENT_STUDENT_APPLY
                if stage == "supplement_student"
                else BatchStatus.SUPPLEMENT_MENTOR_SELECT
            )
        batch.version_no += 1
        db.commit()
        db.refresh(batch)
        return batch


def check_student_row(db: Session, row: dict[str, Any]) -> tuple[User | None, str | None]:
    user = db.query(User).filter(User.student_no == row["student_no"]).first()
    if not user:
        return None, "学号不存在"
    if user.name != row["name"]:
        return None, "姓名与账号不一致"
    if user.role != "student":
        return None, "账号不是学生"
    if user.status == "disabled" or user.deleted_at is not None:
        return None, "账号已禁用或已删除"
    return user, None


class RosterService:
    @staticmethod
    def preview_students(db: Session, batch_id: int, rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        result = []
        existing = {item.student_no_snapshot for item in db.query(MentorSelectionBatchStudent).filter(
            MentorSelectionBatchStudent.batch_id == batch_id
        ).all()}
        for line, raw in enumerate(rows, 1):
            row = {"student_no": str(raw.get("student_no", "")).strip(), "name": str(raw.get("name", "")).strip(), "class_name": str(raw.get("class_name", "")).strip()}
            error = None
            if not all(row.values()):
                error = "学号、姓名、班级均不能为空"
            elif row["student_no"] in seen:
                error = "文件内学号重复"
            elif row["student_no"] in existing:
                error = "该学生已在批次名单中"
            else:
                _, error = check_student_row(db, row)
            seen.add(row["student_no"])
            result.append({"line": line, **row, "ok": error is None, "error": error})
        return result

    @staticmethod
    def confirm_students(db: Session, batch: MentorSelectionBatch, rows: list[dict[str, Any]]) -> list[MentorSelectionBatchStudent]:
        if batch.status != BatchStatus.DRAFT:
            raise AppException("MENTOR_SELECTION_STAGE_LOCKED", "批次开始后不能导入学生名单", 409)
        if not rows:
            raise AppException("MENTOR_SELECTION_IMPORT_INVALID", "学生名单不能为空", 400)
        checked = RosterService.preview_students(db, batch.id, rows)
        if any(not item["ok"] for item in checked):
            raise AppException("MENTOR_SELECTION_IMPORT_INVALID", "名单预检存在错误，不能确认导入", 400)
        items = []
        for row in rows:
            user = db.query(User).filter(User.student_no == row["student_no"]).first()
            if user is None:
                raise AppException("MENTOR_SELECTION_IMPORT_INVALID", "学生账号不存在", 400)
            item = MentorSelectionBatchStudent(
                batch_id=batch.id, student_id=user.id, student_no_snapshot=user.student_no,
                name_snapshot=user.name, class_name=row["class_name"],
            )
            db.add(item)
            items.append(item)
        db.commit()
        return items

    @staticmethod
    def set_mentors(db: Session, batch: MentorSelectionBatch, teacher_ids: list[int]) -> list[MentorSelectionBatchMentor]:
        if batch.status != BatchStatus.DRAFT:
            raise AppException("MENTOR_SELECTION_STAGE_LOCKED", "批次开始后不能修改导师名单", 409)
        if len(set(teacher_ids)) < 3:
            raise AppException("MENTOR_SELECTION_MENTORS_TOO_FEW", "至少需要 3 名导师", 400)
        users = db.query(User).filter(User.id.in_(teacher_ids), User.role == "teacher", User.status == "active", User.deleted_at.is_(None)).all()
        if len(users) != len(set(teacher_ids)):
            raise AppException("MENTOR_SELECTION_INVALID_MENTOR", "导师名单包含无效账号", 400)
        db.query(MentorSelectionBatchMentor).filter(MentorSelectionBatchMentor.batch_id == batch.id).delete()
        result = [MentorSelectionBatchMentor(batch_id=batch.id, teacher_id=uid) for uid in set(teacher_ids)]
        db.add_all(result)
        db.commit()
        return result

    @staticmethod
    def can_open_main(batch: MentorSelectionBatch, db: Session) -> None:
        student_count = db.query(MentorSelectionBatchStudent).filter_by(batch_id=batch.id).count()
        mentor_count = db.query(MentorSelectionBatchMentor).filter_by(batch_id=batch.id, status="active").count()
        if student_count < 1 or mentor_count < 3:
            raise AppException("MENTOR_SELECTION_ROSTER_INCOMPLETE", "主选开放前至少需要 1 名学生和 3 名有效导师", 400)


def _find_latest_preference(db: Session, batch_id: int, student_id: int, round_name: str, submitted_only=False):
    query = db.query(MentorPreferenceSubmission).filter_by(batch_id=batch_id, student_id=student_id, round=round_name)
    latest = query.order_by(MentorPreferenceSubmission.version.desc()).first()
    if submitted_only and latest and latest.status not in {PreferenceStatus.SUBMITTED, PreferenceStatus.LOCKED}:
        return None
    return latest


def validate_preferences(db: Session, batch: MentorSelectionBatch, student_id: int, round_name: str, personal_statement: str, items: list[dict[str, Any]], submit: bool) -> None:
    if len({item["teacher_id"] for item in items}) != len(items):
        raise AppException("MENTOR_SELECTION_DUPLICATE_MENTOR", "志愿导师不能重复", 400)
    if [item["rank"] for item in items] != list(range(1, len(items) + 1)):
        raise AppException("MENTOR_SELECTION_RANK_INVALID", "志愿排名必须从 1 连续递增", 400)
    allowed = {row.teacher_id for row in db.query(MentorSelectionBatchMentor).filter_by(batch_id=batch.id, status="active").all()}
    if any(item["teacher_id"] not in allowed for item in items):
        raise AppException("MENTOR_SELECTION_INVALID_MENTOR", "志愿中包含未参加本批次的导师", 400)
    if submit:
        minimum, maximum = (3, 4) if round_name == SelectionRound.MAIN else (1, None)
        if len(items) < minimum or maximum is not None and len(items) > maximum:
            raise AppException("MENTOR_SELECTION_PREFERENCE_COUNT", "主选需选择 3-4 位导师，补录至少选择 1 位导师", 400)
        if not personal_statement.strip() or any(not item.get("reason", "").strip() for item in items):
            raise AppException("MENTOR_SELECTION_REASON_REQUIRED", "个人陈述和每位导师理由均不能为空", 400)
        user = db.query(User).filter(User.id == student_id).first()
        profile = user.profile if user else {}
        if not str(profile.get("bio") or "").strip():
            raise AppException("MENTOR_SELECTION_PROFILE_INCOMPLETE", "请先完善个人简介", 400)
        grades = profile.get("course_grades") or []
        if not isinstance(grades, list) or len(grades) < 3:
            raise AppException("MENTOR_SELECTION_PROFILE_INCOMPLETE", "请至少填写 3 门课程成绩", 400)


class PreferenceService:
    @staticmethod
    def save(db: Session, batch: MentorSelectionBatch, student_id: int, data: dict[str, Any]) -> MentorPreferenceSubmission:
        round_name = data.get("round", SelectionRound.MAIN)
        items = data.get("items", [])
        submit = bool(data.get("submit"))
        validate_preferences(db, batch, student_id, round_name, data.get("personal_statement", ""), items, submit)
        latest = _find_latest_preference(db, batch.id, student_id, round_name)
        version = (latest.version + 1) if latest else 1
        pref = MentorPreferenceSubmission(batch_id=batch.id, student_id=student_id, round=round_name, version=version, personal_statement=data.get("personal_statement", ""), status=PreferenceStatus.SUBMITTED if submit else PreferenceStatus.DRAFT, submitted_at=local_now() if submit else None)
        db.add(pref)
        db.flush()
        db.add_all([MentorPreferenceItem(preference_id=pref.id, teacher_id=item["teacher_id"], rank=item["rank"], reason=item.get("reason", "")) for item in items])
        db.commit()
        db.refresh(pref)
        return pref

    @staticmethod
    def withdraw(db: Session, batch: MentorSelectionBatch, student_id: int, round_name: str) -> MentorPreferenceSubmission:
        pref = _find_latest_preference(db, batch.id, student_id, round_name, submitted_only=True)
        if not pref:
            raise AppException("MENTOR_SELECTION_PREFERENCE_NOT_FOUND", "没有可撤回的正式志愿", 404)
        pref.status = PreferenceStatus.WITHDRAWN
        pref.withdrawn_at = local_now()
        db.commit()
        return pref

    @staticmethod
    def lock(db: Session, batch_id: int, round_name: str) -> None:
        prefs = db.query(MentorPreferenceSubmission).filter_by(batch_id=batch_id, round=round_name, status=PreferenceStatus.SUBMITTED).all()
        for pref in prefs:
            pref.status = PreferenceStatus.LOCKED
        db.commit()


def _latest_decision(db: Session, batch_id: int, teacher_id: int, round_name: str):
    return db.query(MentorDecisionSubmission).filter_by(batch_id=batch_id, teacher_id=teacher_id, round=round_name).order_by(MentorDecisionSubmission.version.desc()).first()


class DecisionService:
    @staticmethod
    def save(db: Session, batch: MentorSelectionBatch, teacher_id: int, data: dict[str, Any]) -> MentorDecisionSubmission:
        round_name = data.get("round", SelectionRound.MAIN)
        participation = db.query(MentorSelectionBatchMentor).filter_by(batch_id=batch.id, teacher_id=teacher_id, status="active").first()
        if not participation:
            raise AppException("MENTOR_SELECTION_NOT_PARTICIPANT", "导师未参加本批次", 403)
        latest = _latest_decision(db, batch.id, teacher_id, round_name)
        if latest and latest.status == DecisionStatus.SUBMITTED:
            raise AppException("MENTOR_SELECTION_DECISION_LOCKED", "导师名单已最终提交", 409)
        items = data.get("items", [])
        if len({item["student_id"] for item in items}) != len(items):
            raise AppException("MENTOR_SELECTION_DUPLICATE_STUDENT", "候选学生不能重复", 400)
        if any(item.get("decision") not in {"accepted", "rejected"} for item in items):
            raise AppException("MENTOR_SELECTION_DECISION_INVALID", "决定必须为 accepted 或 rejected", 400)
        candidate_ids: set[int] = set()
        participants = db.query(MentorSelectionBatchStudent).filter_by(batch_id=batch.id).all()
        for participant in participants:
            pref = _find_latest_preference(
                db, batch.id, participant.student_id, round_name, submitted_only=True
            )
            if pref and db.query(MentorPreferenceItem).filter_by(
                preference_id=pref.id, teacher_id=teacher_id
            ).first():
                candidate_ids.add(participant.student_id)
        if any(item["student_id"] not in candidate_ids for item in items):
            raise AppException("MENTOR_SELECTION_NOT_CANDIDATE", "决定中包含未选择您的学生", 403)
        accepted = [item for item in items if item.get("decision") == "accepted"]
        quota = participation.quota - (participation.main_matched_count if round_name == SelectionRound.SUPPLEMENT else 0)
        if len(accepted) > quota:
            raise AppException("MENTOR_SELECTION_QUOTA_EXCEEDED", f"最多接收 {quota} 人", 409)
        submitted = bool(data.get("submit"))
        version = latest.version + 1 if latest else 1
        decision = MentorDecisionSubmission(batch_id=batch.id, teacher_id=teacher_id, round=round_name, version=version, status=DecisionStatus.SUBMITTED if submitted else DecisionStatus.DRAFT, submitted_at=local_now() if submitted else None)
        db.add(decision)
        db.flush()
        db.add_all([MentorDecisionItem(submission_id=decision.id, student_id=item["student_id"], decision=item["decision"]) for item in items])
        db.commit()
        return decision


def calculate_matches(db: Session, batch_id: int, round_name: str, preferences: list[dict[str, Any]], accepted_by_teacher: dict[int, set[int]], capacity: dict[int, int]) -> list[dict[str, Any]]:
    """Pure deterministic matching function used by the service and tests."""
    allowed_teachers = set(capacity)
    by_student: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item in preferences:
        if (
            item["teacher_id"] in allowed_teachers
            and item["student_id"] in accepted_by_teacher.get(item["teacher_id"], set())
        ):
            by_student[item["student_id"]].append(item)
    results = []
    used: defaultdict[int, int] = defaultdict(int)
    for student_id in sorted({item["student_id"] for item in preferences}):
        choices = sorted(by_student.get(student_id, []), key=lambda item: (item["rank"], item["teacher_id"]))
        match = next((choice for choice in choices if used[choice["teacher_id"]] < capacity[choice["teacher_id"]]), None)
        if match:
            used[match["teacher_id"]] += 1
            results.append({"student_id": student_id, "teacher_id": match["teacher_id"], "matched_rank": match["rank"], "status": "matched"})
        else:
            results.append({"student_id": student_id, "teacher_id": None, "matched_rank": None, "status": "unmatched"})
    return results


class MatchService:
    @staticmethod
    def calculate(db: Session, batch: MentorSelectionBatch, round_name: str) -> MentorMatchResultVersion:
        students = db.query(MentorSelectionBatchStudent).filter_by(batch_id=batch.id).all()
        preferences: list[dict[str, Any]] = []
        for student in students:
            pref = _find_latest_preference(db, batch.id, student.student_id, round_name, submitted_only=True)
            if not pref:
                continue
            for item in db.query(MentorPreferenceItem).filter_by(preference_id=pref.id).all():
                preferences.append({"student_id": student.student_id, "teacher_id": item.teacher_id, "rank": item.rank})
        accepted: dict[int, set[int]] = {}
        capacity: dict[int, int] = {}
        for mentor in db.query(MentorSelectionBatchMentor).filter_by(batch_id=batch.id, status="active").all():
            submission = _latest_decision(db, batch.id, mentor.teacher_id, round_name)
            if submission:
                accepted[mentor.teacher_id] = {item.student_id for item in db.query(MentorDecisionItem).filter_by(submission_id=submission.id, decision="accepted").all()}
            else:
                accepted[mentor.teacher_id] = set()
            capacity[mentor.teacher_id] = mentor.quota - (mentor.main_matched_count if round_name == SelectionRound.SUPPLEMENT else 0)
        result_rows = calculate_matches(db, batch.id, round_name, preferences, accepted, capacity)
        previous = db.query(MentorMatchResultVersion).filter_by(batch_id=batch.id, round=round_name).order_by(MentorMatchResultVersion.version.desc()).first()
        version = previous.version + 1 if previous else 1
        result = MentorMatchResultVersion(batch_id=batch.id, round=round_name, version=version, status="calculated")
        db.add(result)
        db.flush()
        db.add_all([MentorMatchResultItem(result_version_id=result.id, **row) for row in result_rows])
        db.commit()
        return result

    @staticmethod
    def publish(db: Session, result: MentorMatchResultVersion, batch: MentorSelectionBatch) -> MentorMatchResultVersion:
        if result.status == "published":
            return result
        items = db.query(MentorMatchResultItem).filter_by(result_version_id=result.id).all()
        if result.round == SelectionRound.SUPPLEMENT and any(item.status == "unmatched" for item in items):
            raise AppException("MENTOR_SELECTION_SUPPLEMENT_BLOCKED", "补录仍有未匹配学生，不能发布", 409)
        db.query(MentorMatchResultVersion).filter(
            MentorMatchResultVersion.batch_id == batch.id,
            MentorMatchResultVersion.round == result.round,
            MentorMatchResultVersion.status == "published",
            MentorMatchResultVersion.id != result.id,
        ).update({MentorMatchResultVersion.status: "void"}, synchronize_session=False)
        matched_counts = Counter(item.teacher_id for item in items if item.teacher_id is not None)
        for mentor in db.query(MentorSelectionBatchMentor).filter_by(batch_id=batch.id).all():
            if result.round == SelectionRound.MAIN:
                mentor.main_matched_count = matched_counts[mentor.teacher_id]
            else:
                mentor.supplement_matched_count = matched_counts[mentor.teacher_id]
        for item in items:
            participant = db.query(MentorSelectionBatchStudent).filter_by(
                batch_id=batch.id, student_id=item.student_id
            ).first()
            if participant:
                participant.status = item.status
        result.status = "published"
        result.published_at = local_now()
        db.commit()
        return result
