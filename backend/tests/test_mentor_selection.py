from datetime import timedelta
from io import BytesIO

import pytest
from fastapi import Depends, Header
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.deps import get_current_user
from backend.app.core.database import Base, get_db, local_now
from backend.app.models.achievement import Achievement
from backend.app.models.mentor_selection import (
    BatchStatus,
    MentorSelectionBatch,
    MentorSelectionBatchMentor,
    MentorSelectionBatchStudent,
    MentorMatchResultVersion,
    MentorPreferenceSubmission,
)
from backend.app.models.user import User
from backend.app.services.mentor_selection_service import (
    BatchStateMachine,
    DecisionService,
    PreferenceService,
    RosterService,
    calculate_matches,
    validate_batch_times,
)
from backend.app.services.profile_service import normalize_profile, validate_mentor_selection_profile

# Resolve every foreign key in the shared metadata before creating the isolated database.
from backend.app.main import app as _app  # noqa: E402, F401


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


@pytest.fixture()
def api_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

    def override_get_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    def override_current_user(
        x_test_user: str = Header(...), db: Session = Depends(get_db)
    ) -> User:
        return db.query(User).filter_by(student_no=x_test_user).one()

    _app.dependency_overrides[get_db] = override_get_db
    _app.dependency_overrides[get_current_user] = override_current_user
    try:
        with TestClient(_app) as client:
            yield client, factory
    finally:
        _app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)


def _times():
    now = local_now() + timedelta(days=1)
    return {
        "student_apply_start": now,
        "student_apply_end": now + timedelta(hours=1),
        "mentor_select_start": now + timedelta(hours=1),
        "mentor_select_end": now + timedelta(hours=2),
        "main_publish_at": now + timedelta(hours=3),
    }


def _user(db, no: str, name: str, role: str):
    user = User(student_no=no, name=name, password_hash="x", role=role, status="active")
    db.add(user)
    db.flush()
    return user


def _batch(db, admin_id: int):
    item = MentorSelectionBatch(
        name="2026 学年双选",
        academic_year="2026-2027",
        term="秋季",
        created_by=admin_id,
        **_times(),
    )
    db.add(item)
    db.flush()
    return item


def test_time_order_and_state_machine_reject_invalid_transition(db):
    admin = _user(db, "A001", "管理员", "admin")
    values = _times()
    validate_batch_times(values)
    invalid = dict(values, mentor_select_end=values["student_apply_end"])
    with pytest.raises(ValueError, match="时间"):
        validate_batch_times(invalid)

    batch = _batch(db, admin.id)
    BatchStateMachine.move(batch, BatchStatus.STUDENT_APPLY)
    assert batch.active_key == "mentor_selection_active"
    with pytest.raises(Exception, match="不能从"):
        BatchStateMachine.move(batch, BatchStatus.MAIN_PUBLISHED)


def test_roster_preview_and_fixed_mentor_quota(db):
    admin = _user(db, "A001", "管理员", "admin")
    student = _user(db, "S001", "张三", "student")
    teachers = [_user(db, f"T00{i}", f"导师{i}", "teacher") for i in range(1, 4)]
    batch = _batch(db, admin.id)
    checked = RosterService.preview_students(
        db, batch.id,
        [
            {"student_no": student.student_no, "name": student.name, "class_name": "英才班"},
            {"student_no": student.student_no, "name": student.name, "class_name": "英才班"},
        ],
    )
    assert checked[0]["ok"] is True
    assert checked[1]["error"] == "文件内学号重复"
    RosterService.confirm_students(db, batch, [checked[0]])
    mentors = RosterService.set_mentors(db, batch, [teacher.id for teacher in teachers])
    assert {mentor.quota for mentor in mentors} == {4}
    RosterService.can_open_main(batch, db)


def test_roster_preview_allows_student_pending_initial_password_change(db):
    admin = _user(db, "A001", "管理员", "admin")
    student = _user(db, "S001", "张三", "student")
    student.status = "pending_change"
    batch = _batch(db, admin.id)
    db.commit()

    checked = RosterService.preview_students(
        db,
        batch.id,
        [{"student_no": student.student_no, "name": student.name, "class_name": "英才班"}],
    )

    assert checked[0]["ok"] is True
    assert checked[0]["error"] is None


def test_formal_preference_requires_profile_and_three_ranked_choices(db):
    admin = _user(db, "A001", "管理员", "admin")
    student = _user(db, "S001", "张三", "student")
    teachers = [_user(db, f"T00{i}", f"导师{i}", "teacher") for i in range(1, 4)]
    batch = _batch(db, admin.id)
    batch.status = BatchStatus.STUDENT_APPLY
    db.add(MentorSelectionBatchStudent(
        batch_id=batch.id, student_id=student.id, student_no_snapshot=student.student_no,
        name_snapshot=student.name, class_name="英才班",
    ))
    db.add_all([MentorSelectionBatchMentor(batch_id=batch.id, teacher_id=t.id) for t in teachers])
    student.profile = {
        "bio": "关注数据科学研究。",
        "course_grades": [
            {"course_name": "数学", "score": "优秀"},
            {"course_name": "统计", "score": "92"},
            {"course_name": "程序设计", "score": "A"},
        ],
    }
    db.commit()
    pref = PreferenceService.save(db, batch, student.id, {
        "round": "main",
        "personal_statement": "希望参与科研训练。",
        "submit": True,
        "items": [
            {"teacher_id": teacher.id, "rank": rank, "reason": f"理由{rank}"}
            for rank, teacher in enumerate(teachers, 1)
        ],
    })
    assert pref.status == "submitted"

    with pytest.raises(Exception, match="3-4"):
        PreferenceService.save(db, batch, student.id, {
            "round": "main", "personal_statement": "说明", "submit": True,
            "items": [{"teacher_id": teachers[0].id, "rank": 1, "reason": "理由"}],
        })


def test_decision_quota_and_candidate_guard(db):
    admin = _user(db, "A001", "管理员", "admin")
    teachers = [_user(db, f"T00{i}", f"导师{i}", "teacher") for i in range(1, 4)]
    batch = _batch(db, admin.id)
    batch.status = BatchStatus.MENTOR_SELECT
    db.add_all([MentorSelectionBatchMentor(batch_id=batch.id, teacher_id=t.id) for t in teachers])
    students = []
    for i in range(5):
        student = _user(db, f"S00{i}", f"学生{i}", "student")
        student.profile = {
            "bio": "简介",
            "course_grades": [
                {"course_name": "A", "score": "1"},
                {"course_name": "B", "score": "2"},
                {"course_name": "C", "score": "3"},
            ],
        }
        db.add(MentorSelectionBatchStudent(
            batch_id=batch.id, student_id=student.id, student_no_snapshot=student.student_no,
            name_snapshot=student.name, class_name="英才班",
        ))
        PreferenceService.save(db, batch, student.id, {
            "round": "main", "personal_statement": "说明", "submit": True,
            "items": [
                {"teacher_id": t.id, "rank": rank, "reason": "理由"}
                for rank, t in enumerate(teachers, 1)
            ],
        })
        students.append(student)
    with pytest.raises(Exception, match="最多接收 4 人"):
        DecisionService.save(db, batch, teachers[0].id, {
            "round": "main", "submit": False,
            "items": [{"student_id": student.id, "decision": "accepted"} for student in students],
        })


def test_matching_is_deterministic_and_uses_teacher_acceptance():
    preferences = [
        {"student_id": 1, "teacher_id": 10, "rank": 1},
        {"student_id": 1, "teacher_id": 20, "rank": 2},
        {"student_id": 2, "teacher_id": 10, "rank": 1},
    ]
    accepted = {10: {2}, 20: {1}}
    result = calculate_matches(None, 1, "main", list(reversed(preferences)), accepted, {10: 4, 20: 4})
    assert result == [
        {"student_id": 1, "teacher_id": 20, "matched_rank": 2, "status": "matched"},
        {"student_id": 2, "teacher_id": 10, "matched_rank": 1, "status": "matched"},
    ]


def test_profile_extension_validates_contact_and_course_grades():
    profile = normalize_profile({
        "bio": "简介", "phone": "13800138000", "email": "student@example.com",
        "course_grades": [
            {"course_name": "高数", "score": "90"},
            {"course_name": "英语", "score": "A"},
            {"course_name": "统计", "score": "优秀", "remark": "专业课"},
        ],
        "gpa": "4.0",
    })
    assert "gpa" not in profile
    validate_mentor_selection_profile(profile)
    with pytest.raises(ValueError, match="邮箱"):
        normalize_profile({"email": "broken"})


def _seed_api_batch(factory):
    with factory() as session:
        admin = _user(session, "A001", "管理员", "admin")
        teacher = _user(session, "T001", "导师一", "teacher")
        other_teacher = _user(session, "T002", "导师二", "teacher")
        third_teacher = _user(session, "T003", "导师三", "teacher")
        _outsider = _user(session, "T004", "导师四", "teacher")
        student = _user(session, "S001", "张三", "student")
        student.profile = {
            "major": "数据科学",
            "phone": "13800138000",
            "email": "student@example.com",
            "bio": "专注数据挖掘与科研训练。",
            "course_grades": [
                {"course_name": "统计学", "score": "95"},
                {"course_name": "程序设计", "score": "92"},
                {"course_name": "线性代数", "score": "90"},
            ],
        }
        batch = _batch(session, admin.id)
        batch.status = BatchStatus.STUDENT_APPLY
        session.add(MentorSelectionBatchStudent(
            batch_id=batch.id, student_id=student.id, student_no_snapshot=student.student_no,
            name_snapshot=student.name, class_name="英才班",
        ))
        session.add_all([
            MentorSelectionBatchMentor(batch_id=batch.id, teacher_id=teacher.id),
            MentorSelectionBatchMentor(batch_id=batch.id, teacher_id=other_teacher.id),
            MentorSelectionBatchMentor(batch_id=batch.id, teacher_id=third_teacher.id),
        ])
        PreferenceService.save(session, batch, student.id, {
            "round": "main", "personal_statement": "希望参与科研项目。", "submit": True,
            "items": [
                {"teacher_id": teacher.id, "rank": 1, "reason": "研究方向契合。"},
                {"teacher_id": other_teacher.id, "rank": 2, "reason": "希望学习方法。"},
                {"teacher_id": third_teacher.id, "rank": 3, "reason": "希望拓展视野。"},
            ],
        })
        session.add(Achievement(
            user_id=student.id, category="award", title="数据竞赛一等奖", level="校级",
            achievement_date="2026-06", status="approved",
        ))
        session.commit()
        return batch.id, student.id


def test_create_batch_returns_validation_error_for_invalid_phase_times(api_client):
    client, factory = api_client
    with factory() as session:
        _user(session, "A001", "管理员", "admin")
        session.commit()
    payload = {
        "name": "时间校验批次", "academic_year": "2026-2027", "term": "秋季",
        "student_apply_start": "2026-09-01T09:00:00+08:00",
        "student_apply_end": "2026-09-01T10:00:00+08:00",
        "mentor_select_start": "2026-09-01T10:00:00+08:00",
        "mentor_select_end": "2026-09-01T11:00:00+08:00",
        "main_publish_at": "2026-09-01T12:00:00+08:00",
        "supplement_student_start": "2026-09-01T11:30:00+08:00",
        "supplement_student_end": "2026-09-01T13:00:00+08:00",
        "supplement_mentor_start": "2026-09-01T13:00:00+08:00",
        "supplement_mentor_end": "2026-09-01T14:00:00+08:00",
        "supplement_publish_at": "2026-09-01T15:00:00+08:00",
    }
    response = client.post(
        "/api/v1/mentor-selection/batches", headers={"x-test-user": "A001"}, json=payload,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MENTOR_SELECTION_INVALID_TIME"
    assert "主选发布时间" in response.json()["error"]["message"]


def test_xlsx_roster_import_then_open_main_selection(api_client):
    client, factory = api_client
    with factory() as session:
        admin = _user(session, "A001", "管理员", "admin")
        student = _user(session, "S001", "张三", "student")
        teachers = [_user(session, f"T00{i}", f"导师{i}", "teacher") for i in range(1, 4)]
        batch = _batch(session, admin.id)
        session.commit()
        batch_id = batch.id
        teacher_ids = [teacher.id for teacher in teachers]
        student_no, student_name = student.student_no, student.name

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["学号", "姓名", "班级"])
    sheet.append([student_no, student_name, "英才班"])
    content = BytesIO()
    workbook.save(content)
    headers = {"x-test-user": "A001"}
    response = client.post(
        f"/api/v1/mentor-selection/batches/{batch_id}/students/import/preview",
        headers=headers,
        files={"file": ("学生名单.xlsx", content.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 200
    preview = response.json()
    assert preview["valid"] == 1
    response = client.post(
        f"/api/v1/mentor-selection/batches/{batch_id}/students/import/confirm",
        headers=headers, json={"rows": preview["rows"]},
    )
    assert response.status_code == 200
    assert response.json()["count"] == 1
    response = client.put(
        f"/api/v1/mentor-selection/batches/{batch_id}/mentors",
        headers=headers, json={"teacher_ids": teacher_ids},
    )
    assert response.status_code == 200
    response = client.post(
        f"/api/v1/mentor-selection/batches/{batch_id}/open", headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == BatchStatus.STUDENT_APPLY


def test_advance_endpoint_requires_confirmation_and_follows_phase_order(api_client):
    client, factory = api_client
    batch_id, _ = _seed_api_batch(factory)

    response = client.post(
        f"/api/v1/mentor-selection/batches/{batch_id}/advance",
        headers={"x-test-user": "A001"}, json={"confirm": False},
    )
    assert response.status_code == 400

    response = client.post(
        f"/api/v1/mentor-selection/batches/{batch_id}/advance",
        headers={"x-test-user": "A001"}, json={"confirm": True},
    )
    assert response.status_code == 200
    assert response.json()["status"] == BatchStatus.MENTOR_SELECT
    with factory() as session:
        assert session.query(MentorPreferenceSubmission).one().status == "locked"

    response = client.post(
        f"/api/v1/mentor-selection/batches/{batch_id}/advance",
        headers={"x-test-user": "A001"}, json={"confirm": True},
    )
    assert response.status_code == 200
    assert response.json()["status"] == BatchStatus.MAIN_PENDING
    with factory() as session:
        assert session.query(MentorMatchResultVersion).one().status == "calculated"


def test_accepted_decision_is_published_to_student(api_client):
    client, factory = api_client
    batch_id, student_id = _seed_api_batch(factory)
    admin_headers = {"x-test-user": "A001"}

    response = client.post(
        f"/api/v1/mentor-selection/batches/{batch_id}/advance",
        headers=admin_headers, json={"confirm": True},
    )
    assert response.status_code == 200
    assert response.json()["status"] == BatchStatus.MENTOR_SELECT

    response = client.put(
        f"/api/v1/mentor-selection/batches/{batch_id}/decisions/mine",
        headers={"x-test-user": "T001"},
        json={"round": "main", "submit": True, "items": [
            {"student_id": student_id, "decision": "accepted"},
        ]},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "submitted"

    response = client.post(
        f"/api/v1/mentor-selection/batches/{batch_id}/advance",
        headers=admin_headers, json={"confirm": True},
    )
    assert response.status_code == 200
    assert response.json()["status"] == BatchStatus.MAIN_PENDING
    response = client.post(
        f"/api/v1/mentor-selection/batches/{batch_id}/advance",
        headers=admin_headers, json={"confirm": True},
    )
    assert response.status_code == 200
    assert response.json()["status"] == BatchStatus.MAIN_PUBLISHED

    response = client.get(
        f"/api/v1/mentor-selection/batches/{batch_id}/results/mine",
        headers={"x-test-user": "S001"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "matched"
    assert response.json()["teacher"]["name"] == "导师一"


def test_candidate_detail_is_scoped_to_teacher_and_hidden_after_publication(api_client):
    client, factory = api_client
    batch_id, student_id = _seed_api_batch(factory)
    headers = {"x-test-user": "T001"}

    response = client.get(
        f"/api/v1/mentor-selection/batches/{batch_id}/candidates/{student_id}", headers=headers,
    )
    assert response.status_code == 200
    detail = response.json()
    assert detail["profile"]["major"] == "数据科学"
    assert detail["achievements"][0]["title"] == "数据竞赛一等奖"
    assert "rank" not in detail
    assert "other_teachers" not in detail

    response = client.get(
        f"/api/v1/mentor-selection/batches/{batch_id}/candidates/{student_id}",
        headers={"x-test-user": "T004"},
    )
    assert response.status_code == 403
    response = client.get(
        f"/api/v1/mentor-selection/batches/{batch_id}/candidates/{student_id}",
        headers={"x-test-user": "A001"},
    )
    assert response.status_code == 403

    with factory() as session:
        batch = session.get(MentorSelectionBatch, batch_id)
        batch.status = BatchStatus.MAIN_PUBLISHED
        session.commit()
    response = client.get(
        f"/api/v1/mentor-selection/batches/{batch_id}/candidates/{student_id}", headers=headers,
    )
    assert response.status_code == 403
