from types import SimpleNamespace

import pytest

from backend.app.services.knowledge_scope import (
    InvalidKnowledgeScope,
    KnowledgeScope,
    KnowledgeScopeGuard,
)


def test_scope_guard_rejects_legacy_all():
    with pytest.raises(InvalidKnowledgeScope):
        KnowledgeScopeGuard.parse("all")


def test_scope_guard_builds_isolated_personal_partition():
    user = SimpleNamespace(id=7, profile={}, party={})
    context = KnowledgeScopeGuard.authorize(None, user, "personal")
    assert context.scope is KnowledgeScope.PERSONAL
    assert context.index_key == "personal:7"
    assert context.cache_partition == "chat:7:personal:-"


def test_scope_guard_requires_class_membership():
    user = SimpleNamespace(id=7, profile={}, party={})
    with pytest.raises(PermissionError):
        KnowledgeScopeGuard.authorize(None, user, "class")


def test_scope_guard_none_has_no_index():
    user = SimpleNamespace(id=7, profile={}, party={})
    context = KnowledgeScopeGuard.authorize(None, user, "none")
    assert context.scope is KnowledgeScope.NONE
    assert context.index_key is None


def test_scope_guard_accepts_legacy_class_name_membership_as_stable_partition():
    user = SimpleNamespace(id=7, profile={}, party={"class_name": "大数据25级"})
    context = KnowledgeScopeGuard.authorize(None, user, "class")
    assert context.class_id is not None
    assert context.index_key == f"class:{context.class_id}"
