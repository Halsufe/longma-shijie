from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.config import settings
from backend.app.core.database import Base, local_now
from backend.app.models.achievement import Achievement
from backend.app.models.resource import Resource
from backend.app.models.skill_embedding import SkillEmbedding
from backend.app.models.teacher import TeacherDirection
from backend.app.models.user import User
from backend.app.repositories.resource_repo import ResourceRepository
from backend.app.repositories.skill_embedding_repo import SkillEmbeddingRepository
from backend.app.repositories.teacher_repo import TeacherRepository
from backend.app.repositories.user_repo import UserRepository
from backend.app.services.semantic_service import SemanticService


class FakeModel:
    def encode(self, texts, **kwargs):
        vectors = []
        for text in texts:
            vectors.append([1.0, 0.0] if "机器学习" in text else [0.0, 1.0])
        return vectors


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def fake_semantic_model():
    old_model = SemanticService._model
    old_failed = SemanticService._model_failed
    SemanticService._model = FakeModel()
    SemanticService._model_failed = False
    try:
        yield
    finally:
        SemanticService._model = old_model
        SemanticService._model_failed = old_failed


def _user(db, *, role="student", name="测试用户"):
    user = User(
        student_no=f"NO-{db.query(User).count() + 1}",
        name=name,
        password_hash="hash",
        role=role,
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_embedding_repository_upsert_delete_and_stale(db):
    created = SkillEmbeddingRepository.upsert(
        db,
        entity_type="competition",
        entity_id=1,
        source_text="旧文本",
        embedding=[1.0, 0.0],
    )
    updated = SkillEmbeddingRepository.upsert(
        db,
        entity_type="competition",
        entity_id=1,
        source_text="新文本",
        embedding=[0.0, 1.0],
        version=2,
    )

    assert created.id == updated.id
    assert updated.source_text == "新文本"
    assert updated.embedding == [0.0, 1.0]
    assert updated.version == 2
    assert len(SkillEmbeddingRepository.list_by_type(db, "competition")) == 1
    assert SkillEmbeddingRepository.list_stale(db, "competition", local_now() + timedelta(seconds=1))
    assert SkillEmbeddingRepository.delete_by_entity(db, "competition", 1) == 1
    assert SkillEmbeddingRepository.list_by_type(db, "competition") == []


def test_normalize_cosine_and_weighted_search(db, monkeypatch):
    monkeypatch.setattr(settings, "SEMANTIC_MIN_SCORE", 0.35)
    SkillEmbeddingRepository.upsert(
        db,
        entity_type="competition",
        entity_id=10,
        source_text="机器学习 数据竞赛",
        embedding=[1.0, 0.0],
    )
    SkillEmbeddingRepository.upsert(
        db,
        entity_type="competition",
        entity_id=11,
        source_text="文学竞赛",
        embedding=[0.0, 1.0],
    )

    assert SemanticService.normalize([3.0, 4.0]) == pytest.approx([0.6, 0.8])
    assert SemanticService.cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    results = SemanticService.search(
        db,
        entity_type="competition",
        query_text="机器学习",
        popularity={10: 1.0},
    )

    assert results == [{"entity_id": 10, "score": 1.0}]


def test_search_falls_back_when_model_or_threshold_has_no_result(db, monkeypatch):
    fallback = lambda: [{"entity_id": 99, "score": 0.0}]
    SemanticService._model = None
    SemanticService._model_failed = True
    assert SemanticService.search(
        db, entity_type="competition", query_text="任意", fallback=fallback
    ) == fallback()

    SemanticService._model = FakeModel()
    SemanticService._model_failed = False
    monkeypatch.setattr(settings, "SEMANTIC_MIN_SCORE", 1.1)
    SkillEmbeddingRepository.upsert(
        db,
        entity_type="competition",
        entity_id=1,
        source_text="机器学习",
        embedding=[1.0, 0.0],
    )
    assert SemanticService.search(
        db, entity_type="competition", query_text="机器学习", fallback=fallback
    ) == fallback()


def test_resource_refresh_hooks_create_update_status_and_delete(db):
    author = _user(db)
    resource = ResourceRepository.create(
        db,
        author.id,
        type="competition",
        title="机器学习挑战赛",
        content="数据建模",
        status="approved",
    )
    stored = SkillEmbeddingRepository.list_by_type(db, "competition")
    assert [item.entity_id for item in stored] == [resource.id]

    ResourceRepository.update(db, resource, title="机器学习应用赛")
    assert "应用赛" in SkillEmbeddingRepository.list_by_type(db, "competition")[0].source_text
    ResourceRepository.update_status(db, resource.id, "rejected")
    assert SkillEmbeddingRepository.list_by_type(db, "competition") == []
    ResourceRepository.update_status(db, resource.id, "approved")
    assert len(SkillEmbeddingRepository.list_by_type(db, "competition")) == 1
    ResourceRepository.soft_delete(db, resource)
    assert SkillEmbeddingRepository.list_by_type(db, "competition") == []


def test_teacher_direction_and_profile_refresh_hooks(db):
    teacher = _user(db, role="teacher", name="张老师")
    direction = TeacherRepository.create_direction(
        db,
        teacher.id,
        title="机器学习",
        description="自然语言处理",
        tags_json='["NLP"]',
    )
    assert [item.entity_id for item in SkillEmbeddingRepository.list_by_type(db, "teacher_direction")] == [
        direction.id
    ]

    TeacherRepository.update_direction(db, direction, title="大语言模型")
    assert "大语言模型" in SkillEmbeddingRepository.list_by_type(db, "teacher_direction")[0].source_text
    TeacherRepository.soft_delete_direction(db, direction)
    assert SkillEmbeddingRepository.list_by_type(db, "teacher_direction") == []

    UserRepository.set_profile(db, teacher, {"research": "机器学习", "skills": ["NLP"]})
    profile_embedding = SkillEmbeddingRepository.list_by_type(db, "teacher_profile")
    assert len(profile_embedding) == 1
    assert "张老师" in profile_embedding[0].source_text
