from __future__ import annotations

import csv
import io
import json
from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.errors import AppException
from backend.app.models.party import PartyActivity, PartyActivityParticipant
from backend.app.models.user import User
from backend.app.services.party_archive_service import PartyArchiveService
from backend.app.services.party_stats_service import PartyStatsService


EXPORT_LIMIT = 5000


class PartyExportService:
    @staticmethod
    def _csv(
        headers: list[str], rows: list[list[Any]], max_rows: int = EXPORT_LIMIT
    ) -> str:
        limit = min(max_rows, EXPORT_LIMIT)
        if len(rows) > limit:
            raise AppException(
                "PARTY_EXPORT_LIMIT_EXCEEDED",
                f"单次最多导出 {limit} 条记录，请缩小筛选范围",
                422,
            )
        stream = io.StringIO(newline="")
        stream.write("\ufeff")
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows(rows)
        return stream.getvalue()

    @staticmethod
    def export(
        db: Session,
        *,
        export_type: str,
        class_name: str | None = None,
        grade: str | None = None,
        year: int | None = None,
        category: str | None = None,
        party_type: str | None = None,
        apply_status: str | None = None,
        activity_id: int | None = None,
        max_rows: int = EXPORT_LIMIT,
        format: str = "csv",
    ) -> tuple[str, str]:
        if format != "csv":
            raise AppException("PARTY_EXPORT_FORMAT_INVALID", "本期仅支持 CSV 导出", 422)
        if export_type == "members":
            members = PartyArchiveService.list_members(
                db,
                class_name=class_name,
                grade=grade,
                party_type=party_type,
                apply_status=apply_status,
            )
            rows = [
                [
                    user.student_no,
                    user.name,
                    user.party.get("party_type", ""),
                    user.party.get("apply_status", ""),
                    user.party.get("branch_name", ""),
                    user.party.get("class_name", ""),
                    user.party.get("grade", ""),
                    user.party.get("apply_date", ""),
                    user.party.get("full_date", ""),
                ]
                for user in members
            ]
            return "party-members.csv", PartyExportService._csv(
                [
                    "学号",
                    "姓名",
                    "党员类型",
                    "发展阶段",
                    "支部",
                    "班级",
                    "年级",
                    "申请时间",
                    "转正时间",
                ],
                rows,
                max_rows,
            )

        if export_type == "participants":
            query = (
                db.query(PartyActivityParticipant, PartyActivity, User)
                .join(
                    PartyActivity,
                    PartyActivity.id == PartyActivityParticipant.activity_id,
                )
                .join(User, User.id == PartyActivityParticipant.user_id)
                .filter(PartyActivity.deleted_at.is_(None))
            )
            items = query.order_by(
                PartyActivity.start_at.desc(), User.student_no.asc()
            ).all()
            rows = []
            for participant, activity, user in items:
                if year and activity.start_at.year != year:
                    continue
                if activity_id and activity.id != activity_id:
                    continue
                if category and activity.category != category:
                    continue
                if class_name and user.party.get("class_name") != class_name:
                    continue
                if grade and user.party.get("grade") != grade:
                    continue
                rows.append(
                    [
                        activity.id,
                        activity.title,
                        activity.category,
                        activity.start_at.isoformat(),
                        user.student_no,
                        user.name,
                        participant.registration_status,
                        participant.attendance_status,
                        participant.sign_in_method or "",
                        participant.sign_in_time.isoformat()
                        if participant.sign_in_time
                        else "",
                    ]
                )
            return "party-participants.csv", PartyExportService._csv(
                [
                    "活动ID",
                    "活动名称",
                    "活动类别",
                    "开始时间",
                    "学号",
                    "姓名",
                    "报名状态",
                    "签到状态",
                    "签到方式",
                    "签到时间",
                ],
                rows,
                max_rows,
            )

        if export_type == "stats":
            stats = PartyStatsService.build(
                db,
                class_name=class_name,
                grade=grade,
                year=year,
                category=category,
            )
            rows = [
                ["党员档案数", stats["member_counts"]["total"]],
                ["应参加人次", stats["participation"]["expected_count"]],
                ["报名人次", stats["participation"]["registered_count"]],
                ["签到人次", stats["participation"]["signed_in_count"]],
                ["报名率", stats["participation"]["registration_rate"]],
                ["参与率", stats["participation"]["participation_rate"]],
                ["材料上传量", stats["materials"]["total"]],
                ["年度转正数", stats["development"]["annual_full_count"]],
                ["筛选条件", json.dumps(stats["filters"], ensure_ascii=False)],
            ]
            return "party-stats.csv", PartyExportService._csv(
                ["指标", "值"], rows, max_rows
            )

        raise AppException(
            "PARTY_EXPORT_TYPE_INVALID",
            "export_type 仅支持 stats、members、participants",
            422,
        )
