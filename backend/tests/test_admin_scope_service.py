from types import SimpleNamespace

from backend.app.services.admin_scope_service import can_manage_user, managed_class_ids


def test_managed_class_scope_rejects_out_of_scope_users():
    admin = SimpleNamespace(
        profile={"managed_class_ids": [101, "102"]}, party={}, role="admin"
    )
    in_scope = SimpleNamespace(profile={"class_id": 101}, party={}, role="student")
    out_scope = SimpleNamespace(profile={"class_id": 999}, party={}, role="student")
    assert managed_class_ids(admin) == {101, 102}
    assert can_manage_user(admin, in_scope)
    assert not can_manage_user(admin, out_scope)


def test_legacy_admin_without_mapping_remains_global():
    admin = SimpleNamespace(profile={}, party={}, role="admin")
    target = SimpleNamespace(profile={"class_id": 999}, party={}, role="student")
    assert managed_class_ids(admin) is None
    assert can_manage_user(admin, target)
