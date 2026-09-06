"""Single source of truth for party activity audience matching."""

from backend.app.models.user import User
from backend.app.services.party_political_status_service import (
    PartyPoliticalStatusService,
)

LEAGUE_ACTIVITY_CATEGORIES = {"主题团日", "团学实践", "团组织建设", "其他团学"}

TARGET_ROLES = {
    "全体党员",
    "党员与积极分子",
    "预备党员与积极分子",
    "全体团员",
    "党员与团员",
    "全体学生",
    "群众",
    "指定人员",
}


def political_status(user: User) -> str:
    """Return the effective status, retaining compatibility with old party_json rows."""
    status = PartyPoliticalStatusService.effective_status(user)
    if (
        status != "群众"
        or user.political_status_updated_at is not None
        or user.party.get("deleted_at")
    ):
        return status
    party_type = user.party.get("party_type")
    return {
        "正式党员": "中共党员",
        "预备党员": "预备党员",
        "入党积极分子": "入党积极分子",
    }.get(str(party_type) if party_type is not None else "", status)


def matches_target_role(user: User, target_role: str) -> bool:
    if target_role == "指定人员":
        return False
    if not user.is_student:
        return False
    status = political_status(user)
    if target_role == "全体学生":
        return True
    if target_role == "群众":
        return status == "群众"
    if target_role == "全体团员":
        return status == "共青团员"
    if target_role == "党员与团员":
        return status in {"中共党员", "预备党员", "入党积极分子", "共青团员"}
    if target_role == "全体党员":
        return status in {"中共党员", "预备党员"}
    if target_role == "党员与积极分子":
        return status in {"中共党员", "预备党员", "入党积极分子"}
    if target_role == "预备党员与积极分子":
        return status in {"预备党员", "入党积极分子"}
    return False
