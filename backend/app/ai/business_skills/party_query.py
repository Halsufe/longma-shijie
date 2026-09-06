"""Read-only party query business Skill."""

import re
from typing import Any

from sqlalchemy.orm import Session

from backend.app.ai.business_skills.base import (
    BusinessSkillExecutor,
    BusinessSkillPermissionError,
)
from backend.app.models.user import User
from backend.app.ai.retriever import RAGService
from backend.app.services.party_skill_boundary import PartySkillBoundary


class PartyQueryExecutor(BusinessSkillExecutor):
    skill_name = "party_query"

    _ADMIN_QUERY_TERMS = ("党员名册", "党员名单", "全部党员", "党员统计", "统计党员", "党员有多少")
    _SENSITIVE_TERMS = ("发展材料", "思想汇报", "入党申请", "政审材料")

    async def execute(self, user_input: str, user: User, db: Session) -> dict[str, Any]:
        query = self.normalize_input(user_input)
        query_type = self._query_type(query)
        boundary = PartySkillBoundary(db, user)
        if query_type == "member_list":
            if not user.is_admin:
                raise BusinessSkillPermissionError("仅管理员可查询党员名册或党员统计")
            data = boundary.list_party_members(
                class_name=self._parse_option(query, "class_name"),
                page_size=self._parse_limit(query),
            )
        elif query_type == "member_detail":
            user_id = self._parse_id(query, "user") or user.id
            data = boundary.get_party_member(user_id)
        elif query_type == "my_records":
            data = boundary.get_party_my_records()
        elif query_type == "activity_detail":
            activity_id = self._parse_id(query, "activity")
            if activity_id is None:
                return self._missing_id_result(query_type, query, "请提供活动 ID，例如“活动 3 的详情”。")
            data = boundary.get_party_activity(activity_id)
        else:
            data = boundary.list_party_activities(
                status=self._parse_option(query, "status"),
                category=self._parse_option(query, "category"),
                year=self._parse_year(query),
                page_size=self._parse_limit(query),
            )

        citations: list[dict[str, Any]] = []
        if query_type == "materials":
            rag_results = RAGService.search(db, query, scope="class", user_id=user.id)
            citations = [
                result for result in rag_results
                if not any(
                    term in f"{result.get('file_name', '')} {result.get('chunk_content', '')}"
                    for term in self._SENSITIVE_TERMS
                )
            ]

        return {
            "intent": "query",
            "query_type": query_type,
            "query": query,
            "read_only": True,
            "data": data,
            "items": data.get("items", []) if isinstance(data, dict) else [],
            "total": data.get("total", 1) if isinstance(data, dict) else 1,
            "citations": [
                {
                    "file_id": result.get("file_id"),
                    "file_name": result.get("file_name"),
                    "page_no": result.get("page_no"),
                    "preview": str(result.get("chunk_content", ""))[:200],
                }
                for result in citations
            ],
            "message": "已按当前用户权限完成只读党建查询。",
        }

    def _query_type(self, user_input: str) -> str:
        if any(term in user_input for term in self._ADMIN_QUERY_TERMS):
            return "member_list"
        if any(term in user_input for term in ("我的党员信息", "本人党员信息")):
            return "member_detail"
        if any(term in user_input for term in ("我的党建", "我的活动记录", "报名记录", "签到记录")):
            return "my_records"
        if any(term in user_input for term in ("学习材料", "活动材料", "材料内容")):
            return "materials"
        if "活动" in user_input and any(term in user_input for term in ("详情", "几点", "地点", "开始")):
            return "activity_detail"
        if "党员" in user_input and re.search(r"(?:user_id|党员)\s*[=:：#]?\s*\d+", user_input):
            return "member_detail"
        return "activities"

    @staticmethod
    def _parse_id(query: str, entity: str) -> int | None:
        labels = "activity_id|活动" if entity == "activity" else "user_id|党员"
        match = re.search(rf"(?:{labels})\s*[=:：#]?\s*(\d+)", query, re.IGNORECASE)
        return int(match.group(1)) if match else None

    @staticmethod
    def _parse_option(query: str, name: str) -> str | None:
        match = re.search(rf"{name}\s*[=:：]\s*([^,，\s]+)", query, re.IGNORECASE)
        return match.group(1).strip() if match else None

    @staticmethod
    def _parse_year(query: str) -> int | None:
        match = re.search(r"(20\d{2})\s*年?", query)
        return int(match.group(1)) if match else None

    @staticmethod
    def _parse_limit(query: str) -> int:
        match = re.search(r"(?:limit\s*[=:]?|前)\s*(\d+)", query, re.IGNORECASE)
        return max(1, min(int(match.group(1)), 100)) if match else 20

    @staticmethod
    def _missing_id_result(query_type: str, query: str, message: str) -> dict[str, Any]:
        return {
            "intent": "query",
            "query_type": query_type,
            "query": query,
            "read_only": True,
            "items": [],
            "total": 0,
            "message": message,
        }
