import pytest

from backend.tests.test_party_achievement_link import (
    _activity,
    _headers,
    _user,
)

pytest_plugins = ("backend.tests.test_party_achievement_link",)


def test_league_activity_link_requires_sign_in_and_category(link_client):
    client, session_factory = link_client
    with session_factory() as db:
        user = _user(db, "plain")
        activity_id = _activity(db, user=user, category="主题团日").id
    missing_category = client.post(
        "/api/v1/party/achievements/link",
        json={"link_type": "league_activity", "activity_id": activity_id},
        headers=_headers("plain"),
    )
    assert missing_category.status_code == 422
    linked = client.post(
        "/api/v1/party/achievements/link",
        json={"link_type": "league_activity", "activity_id": activity_id, "achievement_category": "social"},
        headers=_headers("plain"),
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["category"] == "social"
    duplicate = client.post(
        "/api/v1/party/achievements/link",
        json={"link_type": "league_activity", "activity_id": activity_id, "achievement_category": "social"},
        headers=_headers("plain"),
    )
    assert duplicate.status_code == 409


def test_league_activity_link_rejects_unsigned_and_identity(link_client):
    client, session_factory = link_client
    with session_factory() as db:
        user = _user(db, "plain")
        activity_id = _activity(db, user=user, category="团学实践", attendance_status="none").id
    denied = client.post(
        "/api/v1/party/achievements/link",
        json={"link_type": "league_activity", "activity_id": activity_id, "achievement_category": "organization"},
        headers=_headers("plain"),
    )
    assert denied.status_code == 409
    assert "identity" not in denied.text
