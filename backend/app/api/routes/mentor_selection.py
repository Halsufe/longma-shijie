"""API routes for the academic mentor selection workflow."""
import csv
import io

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, require_admin, require_teacher_or_admin
from backend.app.core.database import get_db
from backend.app.core.errors import AppException
from backend.app.models.mentor_selection import (
    BatchStatus, MentorDecisionSubmission, MentorMatchResultItem, MentorMatchResultVersion,
    MentorPreferenceItem, MentorPreferenceSubmission, MentorSelectionBatch,
    MentorSelectionBatchMentor, MentorSelectionBatchStudent, PreferenceStatus, SelectionRound,
)
from backend.app.models.teacher import TeacherDirection
from backend.app.models.achievement import Achievement
from backend.app.models.user import User
from backend.app.schemas.mentor_selection import (
    AdvanceRequest, BatchCreate, BatchUpdate, DecisionInput, ExtendRequest, ImportConfirm,
    MentorRosterUpdate, PreferenceInput, ReopenRequest,
)
from backend.app.services.mentor_selection_service import (
    BatchService, BatchStateMachine, DecisionService, MatchService, PreferenceService, RosterService,
)

router = APIRouter()

_ROSTER_HEADERS = {
    "学号": "student_no", "姓名": "name", "班级": "class_name",
    "student_no": "student_no", "name": "name", "class_name": "class_name",
}


def _normalize_sheet_rows(rows) -> list[dict]:
    values = list(rows)
    if not values:
        return []
    headers = [_ROSTER_HEADERS.get(str(value or "").strip(), str(value or "").strip()) for value in values[0]]
    return [
        {headers[index]: str(value or "").strip() for index, value in enumerate(row) if index < len(headers)}
        for row in values[1:]
        if any(value not in (None, "") for value in row)
    ]


def _parse_roster_file(filename: str, content: bytes) -> list[dict]:
    suffix = filename.lower().rsplit(".", 1)[-1]
    if suffix == "csv":
        reader = csv.reader(io.StringIO(content.decode("utf-8-sig")))
        return _normalize_sheet_rows(reader)
    if suffix == "xlsx":
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise AppException("MENTOR_SELECTION_EXCEL_UNAVAILABLE", "服务端未安装 XLSX 解析依赖", 503) from exc
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=False, keep_links=False)
        return _normalize_sheet_rows(workbook.active.iter_rows(values_only=True))
    if suffix == "xls":
        try:
            import xlrd
        except ImportError as exc:
            raise AppException("MENTOR_SELECTION_EXCEL_UNAVAILABLE", "服务端未安装 XLS 解析依赖", 503) from exc
        sheet = xlrd.open_workbook(file_contents=content, on_demand=True).sheet_by_index(0)
        return _normalize_sheet_rows(sheet.row_values(index) for index in range(sheet.nrows))
    raise AppException("MENTOR_SELECTION_FILE_TYPE", "仅支持 CSV、XLSX、XLS 文件", 400)


def _batch_or_404(db: Session, batch_id: int) -> MentorSelectionBatch:
    item = db.query(MentorSelectionBatch).filter(
        MentorSelectionBatch.id == batch_id, MentorSelectionBatch.deleted_at.is_(None)
    ).first()
    if not item:
        raise AppException("NOT_FOUND", "双选批次不存在", 404)
    return item


def _batch_dict(batch: MentorSelectionBatch) -> dict:
    return {
        "id": batch.id, "name": batch.name, "academic_year": batch.academic_year, "term": batch.term,
        "status": batch.status, "version_no": batch.version_no,
        "student_apply_start": batch.student_apply_start, "student_apply_end": batch.student_apply_end,
        "mentor_select_start": batch.mentor_select_start, "mentor_select_end": batch.mentor_select_end,
        "main_publish_at": batch.main_publish_at, "supplement_student_start": batch.supplement_student_start,
        "supplement_student_end": batch.supplement_student_end,
        "supplement_mentor_start": batch.supplement_mentor_start,
        "supplement_mentor_end": batch.supplement_mentor_end,
        "supplement_publish_at": batch.supplement_publish_at,
        "created_by": batch.created_by, "created_at": batch.created_at, "updated_at": batch.updated_at,
    }


def _round_for_batch(batch: MentorSelectionBatch) -> str:
    return SelectionRound.SUPPLEMENT if batch.status.startswith("supplement") else SelectionRound.MAIN


@router.post("/batches")
def create_batch(form: BatchCreate, current_user=Depends(require_admin), db: Session = Depends(get_db)):
    return _batch_dict(BatchService.create(db, form.model_dump(), current_user.id))


@router.get("/batches")
def list_batches(
    current_user=Depends(require_admin), db: Session = Depends(get_db),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1),
):
    query = db.query(MentorSelectionBatch).filter(
        MentorSelectionBatch.deleted_at.is_(None)
    ).order_by(MentorSelectionBatch.id.desc())
    total = query.count()
    return {
        "total": total,
        "items": [_batch_dict(item) for item in query.offset((page - 1) * page_size).limit(page_size).all()],
    }


@router.get("/batches/{batch_id}")
def get_batch(batch_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    batch = _batch_or_404(db, batch_id)
    result = _batch_dict(batch)
    result["student_count"] = db.query(MentorSelectionBatchStudent).filter_by(batch_id=batch.id).count()
    result["mentor_count"] = db.query(MentorSelectionBatchMentor).filter_by(
        batch_id=batch.id, status="active"
    ).count()
    return result


@router.put("/batches/{batch_id}")
def update_batch(
    batch_id: int, form: BatchUpdate, current_user=Depends(require_admin), db: Session = Depends(get_db)
):
    return _batch_dict(
        BatchService.update(db, _batch_or_404(db, batch_id), form.model_dump(exclude_unset=True))
    )


@router.post("/batches/{batch_id}/extend")
def extend_batch(
    batch_id: int, form: ExtendRequest, current_user=Depends(require_admin), db: Session = Depends(get_db)
):
    return _batch_dict(BatchService.extend(db, _batch_or_404(db, batch_id), form.stage, form.new_end))


@router.post("/batches/{batch_id}/open")
def open_batch(batch_id: int, current_user=Depends(require_admin), db: Session = Depends(get_db)):
    batch = _batch_or_404(db, batch_id)
    if batch.status == BatchStatus.DRAFT:
        RosterService.can_open_main(batch, db)
        BatchStateMachine.move(batch, BatchStatus.STUDENT_APPLY)
        db.commit()
    return _batch_dict(batch)


@router.post("/batches/{batch_id}/advance")
def advance_batch(
    batch_id: int, form: AdvanceRequest, current_user=Depends(require_admin), db: Session = Depends(get_db)
):
    """Move exactly one legal phase forward without modifying matching output."""
    if not form.confirm:
        raise AppException("MENTOR_SELECTION_CONFIRM_REQUIRED", "请确认阶段推进操作", 400)
    batch = _batch_or_404(db, batch_id)
    if batch.status == BatchStatus.STUDENT_APPLY:
        PreferenceService.lock(db, batch.id, SelectionRound.MAIN)
        BatchStateMachine.move(batch, BatchStatus.MENTOR_SELECT)
    elif batch.status == BatchStatus.MENTOR_SELECT:
        MatchService.calculate(db, batch, SelectionRound.MAIN)
        BatchStateMachine.move(batch, BatchStatus.MAIN_PENDING)
    elif batch.status == BatchStatus.MAIN_PENDING:
        result = db.query(MentorMatchResultVersion).filter_by(
            batch_id=batch.id, round=SelectionRound.MAIN
        ).order_by(MentorMatchResultVersion.version.desc()).first()
        if not result:
            raise AppException("MENTOR_SELECTION_RESULT_NOT_FOUND", "请先计算主选结果", 409)
        MatchService.publish(db, result, batch)
        BatchStateMachine.move(batch, BatchStatus.MAIN_PUBLISHED)
    elif batch.status == BatchStatus.MAIN_PUBLISHED:
        if not batch.supplement_student_start:
            raise AppException("MENTOR_SELECTION_SUPPLEMENT_UNCONFIGURED", "请先配置补录时间", 409)
        BatchStateMachine.move(batch, BatchStatus.SUPPLEMENT_STUDENT_APPLY)
    elif batch.status == BatchStatus.SUPPLEMENT_STUDENT_APPLY:
        PreferenceService.lock(db, batch.id, SelectionRound.SUPPLEMENT)
        BatchStateMachine.move(batch, BatchStatus.SUPPLEMENT_MENTOR_SELECT)
    elif batch.status == BatchStatus.SUPPLEMENT_MENTOR_SELECT:
        result = MatchService.calculate(db, batch, SelectionRound.SUPPLEMENT)
        unmatched = db.query(MentorMatchResultItem).filter_by(
            result_version_id=result.id, status="unmatched"
        ).count()
        BatchStateMachine.move(
            batch, BatchStatus.SUPPLEMENT_BLOCKED if unmatched else BatchStatus.SUPPLEMENT_PENDING
        )
    elif batch.status == BatchStatus.SUPPLEMENT_PENDING:
        result = db.query(MentorMatchResultVersion).filter_by(
            batch_id=batch.id, round=SelectionRound.SUPPLEMENT
        ).order_by(MentorMatchResultVersion.version.desc()).first()
        if not result:
            raise AppException("MENTOR_SELECTION_RESULT_NOT_FOUND", "请先计算补录结果", 409)
        MatchService.publish(db, result, batch)
        BatchStateMachine.move(batch, BatchStatus.SUPPLEMENT_PUBLISHED)
        BatchStateMachine.move(batch, BatchStatus.COMPLETED)
    elif batch.status == BatchStatus.SUPPLEMENT_BLOCKED:
        raise AppException("MENTOR_SELECTION_SUPPLEMENT_BLOCKED", "补录仍有未匹配学生，请延长补录阶段", 409)
    else:
        raise AppException("MENTOR_SELECTION_INVALID_TRANSITION", "当前阶段不能手动推进", 409)
    batch.version_no += 1
    db.commit()
    return _batch_dict(batch)


@router.post("/batches/{batch_id}/reopen")
def reopen_batch(
    batch_id: int, form: ReopenRequest, current_user=Depends(require_admin), db: Session = Depends(get_db)
):
    batch = _batch_or_404(db, batch_id)
    allowed = {BatchStatus.MAIN_PUBLISHED, BatchStatus.SUPPLEMENT_PUBLISHED, BatchStatus.COMPLETED, BatchStatus.REOPENED}
    if batch.status not in allowed:
        raise AppException("MENTOR_SELECTION_INVALID_REOPEN", "当前批次状态不能重开", 409)
    if batch.status != BatchStatus.REOPENED:
        BatchStateMachine.move(batch, BatchStatus.REOPENED)
    db.query(MentorMatchResultVersion).filter_by(batch_id=batch.id).update(
        {MentorMatchResultVersion.status: "void"}
    )
    if form.stage == "student":
        db.query(MentorPreferenceSubmission).filter_by(batch_id=batch.id).update(
            {MentorPreferenceSubmission.status: PreferenceStatus.WITHDRAWN}
        )
        BatchStateMachine.move(batch, BatchStatus.STUDENT_APPLY)
    else:
        db.query(MentorDecisionSubmission).filter_by(batch_id=batch.id).update(
            {MentorDecisionSubmission.status: "draft"}
        )
        BatchStateMachine.move(batch, BatchStatus.MENTOR_SELECT)
    db.commit()
    return _batch_dict(batch)


@router.post("/batches/{batch_id}/students/import/preview")
async def preview_students(
    batch_id: int, file: UploadFile | None = File(None), payload: ImportConfirm | None = None,
    current_user=Depends(require_admin), db: Session = Depends(get_db),
):
    _batch_or_404(db, batch_id)
    raw_rows: list[dict] = [row.model_dump() for row in payload.rows] if payload else []
    if file:
        raw_rows = _parse_roster_file(file.filename or "", await file.read())
    checked = RosterService.preview_students(db, batch_id, raw_rows)
    return {
        "total": len(checked), "valid": sum(item["ok"] for item in checked),
        "errors": sum(not item["ok"] for item in checked), "rows": checked,
    }


@router.post("/batches/{batch_id}/students/import/confirm")
def confirm_students(
    batch_id: int, form: ImportConfirm, current_user=Depends(require_admin), db: Session = Depends(get_db)
):
    items = RosterService.confirm_students(
        db, _batch_or_404(db, batch_id), [row.model_dump() for row in form.rows]
    )
    return {"success": True, "count": len(items)}


@router.get("/batches/{batch_id}/students")
def list_students(batch_id: int, current_user=Depends(require_admin), db: Session = Depends(get_db)):
    items = db.query(MentorSelectionBatchStudent).filter_by(
        batch_id=batch_id
    ).order_by(MentorSelectionBatchStudent.id).all()
    return {
        "total": len(items),
        "items": [{
            "id": item.id, "student_id": item.student_id, "student_no": item.student_no_snapshot,
            "name": item.name_snapshot, "class_name": item.class_name, "status": item.status,
        } for item in items],
    }


@router.delete("/batches/{batch_id}/students/{student_id}")
def remove_student(
    batch_id: int, student_id: int, current_user=Depends(require_admin), db: Session = Depends(get_db)
):
    batch = _batch_or_404(db, batch_id)
    if batch.status != BatchStatus.DRAFT:
        raise AppException("MENTOR_SELECTION_STAGE_LOCKED", "批次开始后不能移除学生", 409)
    item = db.query(MentorSelectionBatchStudent).filter_by(
        batch_id=batch.id, student_id=student_id
    ).first()
    if not item:
        raise AppException("NOT_FOUND", "学生不在批次名单中", 404)
    db.delete(item)
    db.commit()
    return {"success": True}


@router.get("/batches/{batch_id}/mentors/candidates")
def mentor_candidates(batch_id: int, current_user=Depends(require_admin), db: Session = Depends(get_db)):
    _batch_or_404(db, batch_id)
    users = db.query(User).filter(
        User.role == "teacher", User.status == "active", User.deleted_at.is_(None)
    ).all()
    return {
        "total": len(users),
        "items": [{
            "id": user.id, "name": user.name, "student_no": user.student_no,
            "profile": {
                key: user.profile.get(key)
                for key in ("title", "department", "bio", "research", "skills")
                if user.profile.get(key) is not None
            },
            "directions": [
                direction.title for direction in db.query(TeacherDirection).filter_by(
                    teacher_id=user.id, deleted_at=None
                ).all()
            ],
        } for user in users],
    }


@router.put("/batches/{batch_id}/mentors")
def set_mentors(
    batch_id: int, form: MentorRosterUpdate, current_user=Depends(require_admin), db: Session = Depends(get_db)
):
    items = RosterService.set_mentors(db, _batch_or_404(db, batch_id), form.teacher_ids)
    return {"success": True, "items": [{"teacher_id": item.teacher_id, "quota": item.quota} for item in items]}


def _active_batch_for_user(db: Session, user: User) -> MentorSelectionBatch | None:
    query = db.query(MentorSelectionBatch).filter(
        MentorSelectionBatch.deleted_at.is_(None), MentorSelectionBatch.status != BatchStatus.COMPLETED
    )
    if user.is_student:
        query = query.join(
            MentorSelectionBatchStudent, MentorSelectionBatchStudent.batch_id == MentorSelectionBatch.id
        ).filter(MentorSelectionBatchStudent.student_id == user.id)
    elif user.is_teacher:
        query = query.join(
            MentorSelectionBatchMentor, MentorSelectionBatchMentor.batch_id == MentorSelectionBatch.id
        ).filter(MentorSelectionBatchMentor.teacher_id == user.id)
    current = query.order_by(MentorSelectionBatch.id.desc()).first()
    if current or user.is_admin:
        return current
    history = db.query(MentorSelectionBatch).filter(
        MentorSelectionBatch.deleted_at.is_(None), MentorSelectionBatch.status == BatchStatus.COMPLETED
    )
    if user.is_student:
        history = history.join(
            MentorSelectionBatchStudent, MentorSelectionBatchStudent.batch_id == MentorSelectionBatch.id
        ).filter(MentorSelectionBatchStudent.student_id == user.id)
    elif user.is_teacher:
        history = history.join(
            MentorSelectionBatchMentor, MentorSelectionBatchMentor.batch_id == MentorSelectionBatch.id
        ).filter(MentorSelectionBatchMentor.teacher_id == user.id)
    return history.order_by(MentorSelectionBatch.id.desc()).first()


@router.get("/current")
def current_selection(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    batch = _active_batch_for_user(db, current_user)
    if not batch:
        return {"batch": None, "stage": None}
    return {"batch": _batch_dict(batch), "stage": batch.status, "round": _round_for_batch(batch)}


@router.get("/batches/{batch_id}/mentors")
def list_batch_mentors(batch_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    batch = _batch_or_404(db, batch_id)
    rows = []
    for membership in db.query(MentorSelectionBatchMentor).filter_by(
        batch_id=batch.id, status="active"
    ).all():
        teacher = db.query(User).filter(User.id == membership.teacher_id).first()
        if teacher is None:
            continue
        applicant_count = db.query(MentorPreferenceItem).join(
            MentorPreferenceSubmission,
            MentorPreferenceItem.preference_id == MentorPreferenceSubmission.id,
        ).filter(
            MentorPreferenceSubmission.batch_id == batch.id,
            MentorPreferenceSubmission.status.in_([PreferenceStatus.SUBMITTED, PreferenceStatus.LOCKED]),
            MentorPreferenceItem.teacher_id == teacher.id,
        ).count()
        rows.append({
            "id": teacher.id, "name": teacher.name, "profile": teacher.profile,
            "application_count": applicant_count,
            "remaining_quota": max(
                0, membership.quota - membership.main_matched_count - membership.supplement_matched_count
            ),
            "directions": [{
                "id": direction.id,
                "title": direction.title,
                "description": direction.description,
                "tags": direction.tags,
            } for direction in db.query(TeacherDirection).filter(
                TeacherDirection.teacher_id == teacher.id,
                TeacherDirection.deleted_at.is_(None),
                TeacherDirection.is_active.is_(True),
            ).order_by(TeacherDirection.id).all()],
        })
    return {"total": len(rows), "items": rows}


@router.get("/batches/{batch_id}/preferences/mine")
def get_my_preference(
    batch_id: int, round: str = Query("main"), current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pref = db.query(MentorPreferenceSubmission).filter_by(
        batch_id=batch_id, student_id=current_user.id, round=round
    ).order_by(MentorPreferenceSubmission.version.desc()).first()
    if not pref:
        return None
    return {
        "id": pref.id, "version": pref.version, "round": pref.round, "status": pref.status,
        "personal_statement": pref.personal_statement,
        "items": [{
            "teacher_id": item.teacher_id, "rank": item.rank, "reason": item.reason
        } for item in db.query(MentorPreferenceItem).filter_by(
            preference_id=pref.id
        ).order_by(MentorPreferenceItem.rank).all()],
    }


@router.put("/batches/{batch_id}/preferences/mine")
def save_my_preference(
    batch_id: int, form: PreferenceInput, current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    batch = _batch_or_404(db, batch_id)
    if not current_user.is_student:
        raise AppException("FORBIDDEN", "只有学生可以填写志愿", 403)
    if batch.status not in {BatchStatus.STUDENT_APPLY, BatchStatus.SUPPLEMENT_STUDENT_APPLY}:
        raise AppException("MENTOR_SELECTION_STAGE_LOCKED", "当前阶段不允许填写志愿", 409)
    expected_round = SelectionRound.SUPPLEMENT if batch.status == BatchStatus.SUPPLEMENT_STUDENT_APPLY else SelectionRound.MAIN
    if form.round != expected_round:
        raise AppException("MENTOR_SELECTION_ROUND_INVALID", "填报轮次与当前阶段不一致", 409)
    membership = db.query(MentorSelectionBatchStudent).filter_by(
        batch_id=batch.id, student_id=current_user.id
    ).first()
    if not membership:
        raise AppException("FORBIDDEN", "不在本批次学生名单中", 403)
    pref = PreferenceService.save(db, batch, current_user.id, form.model_dump())
    return {"id": pref.id, "version": pref.version, "status": pref.status}


@router.post("/batches/{batch_id}/preferences/mine/withdraw")
def withdraw_my_preference(
    batch_id: int, round: str = Query("main"), current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    batch = _batch_or_404(db, batch_id)
    if batch.status not in {BatchStatus.STUDENT_APPLY, BatchStatus.SUPPLEMENT_STUDENT_APPLY}:
        raise AppException("MENTOR_SELECTION_STAGE_LOCKED", "当前阶段不允许撤回志愿", 409)
    return {"status": PreferenceService.withdraw(db, batch, current_user.id, round).status}


@router.get("/batches/{batch_id}/candidates")
def list_candidates(
    batch_id: int, current_user=Depends(require_teacher_or_admin), round: str = Query("main"),
    db: Session = Depends(get_db),
):
    batch = _batch_or_404(db, batch_id)
    if current_user.is_teacher and batch.status in {
        BatchStatus.MAIN_PUBLISHED, BatchStatus.SUPPLEMENT_PUBLISHED, BatchStatus.COMPLETED
    }:
        raise AppException("MENTOR_SELECTION_PROFILE_ACCESS_ENDED", "结果发布后只能查看最终匹配学生", 403)
    teacher_ids = [current_user.id] if current_user.is_teacher else [
        row.teacher_id for row in db.query(MentorSelectionBatchMentor).filter_by(batch_id=batch.id).all()
    ]
    if current_user.is_teacher and not db.query(MentorSelectionBatchMentor).filter_by(
        batch_id=batch.id, teacher_id=current_user.id, status="active"
    ).first():
        raise AppException("FORBIDDEN", "导师未参加本批次", 403)
    rows = []
    for teacher_id in teacher_ids:
        prefs = db.query(MentorPreferenceSubmission).filter(
            MentorPreferenceSubmission.batch_id == batch.id,
            MentorPreferenceSubmission.round == round,
        ).order_by(MentorPreferenceSubmission.student_id, MentorPreferenceSubmission.version.desc()).all()
        seen_students: set[int] = set()
        for pref in prefs:
            if pref.student_id in seen_students:
                continue
            seen_students.add(pref.student_id)
            if pref.status not in {PreferenceStatus.SUBMITTED, PreferenceStatus.LOCKED}:
                continue
            item = db.query(MentorPreferenceItem).filter_by(
                preference_id=pref.id, teacher_id=teacher_id
            ).first()
            if item is None:
                continue
            student = db.query(User).filter(User.id == pref.student_id).first()
            if student is None:
                continue
            profile = student.profile
            rows.append({
                "student_id": student.id, "name": student.name, "student_no": student.student_no,
                "profile": {
                    key: profile.get(key)
                    for key in ("major", "phone", "email", "bio", "course_grades")
                    if profile.get(key) is not None
                },
                "personal_statement": pref.personal_statement,
                "reason": item.reason,
            })
    return {"total": len(rows), "items": rows}


@router.get("/batches/{batch_id}/candidates/{student_id}")
def candidate_detail(
    batch_id: int, student_id: int, round: str = Query("main"),
    current_user=Depends(require_teacher_or_admin), db: Session = Depends(get_db),
):
    batch = _batch_or_404(db, batch_id)
    if current_user.is_teacher and batch.status in {
        BatchStatus.MAIN_PUBLISHED, BatchStatus.SUPPLEMENT_PUBLISHED, BatchStatus.COMPLETED
    }:
        raise AppException("MENTOR_SELECTION_PROFILE_ACCESS_ENDED", "结果发布后只能查看最终匹配学生", 403)
    if not current_user.is_teacher:
        raise AppException("FORBIDDEN", "管理员请通过批次汇总查看候选档案", 403)
    membership = db.query(MentorSelectionBatchMentor).filter_by(
        batch_id=batch.id, teacher_id=current_user.id, status="active"
    ).first()
    if not membership:
        raise AppException("FORBIDDEN", "导师未参加本批次", 403)
    preference = db.query(MentorPreferenceSubmission).filter_by(
        batch_id=batch.id, student_id=student_id, round=round
    ).order_by(MentorPreferenceSubmission.version.desc()).first()
    if not preference or preference.status not in {PreferenceStatus.SUBMITTED, PreferenceStatus.LOCKED}:
        raise AppException("NOT_FOUND", "候选学生不存在", 404)
    item = db.query(MentorPreferenceItem).filter_by(
        preference_id=preference.id, teacher_id=current_user.id
    ).first()
    if not item:
        raise AppException("FORBIDDEN", "学生未选择该导师", 403)
    student = db.query(User).filter(User.id == student_id, User.deleted_at.is_(None)).first()
    if not student:
        raise AppException("NOT_FOUND", "学生不存在", 404)
    profile = student.profile
    achievements = db.query(Achievement).filter(
        Achievement.user_id == student.id,
        Achievement.status == "approved",
        Achievement.deleted_at.is_(None),
    ).order_by(Achievement.created_at.desc()).all()
    return {
        "student_id": student.id,
        "name": student.name,
        "student_no": student.student_no,
        "profile": {
            key: profile.get(key)
            for key in ("major", "phone", "email", "bio", "course_grades")
            if profile.get(key) is not None
        },
        "personal_statement": preference.personal_statement,
        "reason": item.reason,
        "achievements": [{
            "id": achievement.id, "category": achievement.category, "title": achievement.title,
            "description": achievement.description, "achievement_date": achievement.achievement_date,
            "level": achievement.level,
        } for achievement in achievements],
    }


@router.put("/batches/{batch_id}/decisions/mine")
def save_my_decisions(
    batch_id: int, form: DecisionInput, current_user=Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    batch = _batch_or_404(db, batch_id)
    if not current_user.is_teacher:
        raise AppException("FORBIDDEN", "管理员不能代替导师选择", 403)
    if batch.status not in {BatchStatus.MENTOR_SELECT, BatchStatus.SUPPLEMENT_MENTOR_SELECT}:
        raise AppException("MENTOR_SELECTION_STAGE_LOCKED", "当前阶段不允许导师选择", 409)
    expected_round = SelectionRound.SUPPLEMENT if batch.status == BatchStatus.SUPPLEMENT_MENTOR_SELECT else SelectionRound.MAIN
    if form.round != expected_round:
        raise AppException("MENTOR_SELECTION_ROUND_INVALID", "导师选择轮次与当前阶段不一致", 409)
    decision = DecisionService.save(db, batch, current_user.id, form.model_dump())
    return {"id": decision.id, "version": decision.version, "status": decision.status}


@router.post("/batches/{batch_id}/calculate")
def calculate_batch(
    batch_id: int, round: str = Query("main"), current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    batch = _batch_or_404(db, batch_id)
    expected = BatchStatus.MENTOR_SELECT if round == SelectionRound.MAIN else BatchStatus.SUPPLEMENT_MENTOR_SELECT
    if batch.status != expected:
        raise AppException("MENTOR_SELECTION_STAGE_LOCKED", "当前阶段不能计算匹配结果", 409)
    result = MatchService.calculate(db, batch, round)
    return {"id": result.id, "version": result.version, "status": result.status}


@router.post("/batches/{batch_id}/publish")
def publish_batch(
    batch_id: int, round: str = Query("main"), current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    batch = _batch_or_404(db, batch_id)
    expected = BatchStatus.MAIN_PENDING if round == SelectionRound.MAIN else BatchStatus.SUPPLEMENT_PENDING
    if batch.status != expected:
        raise AppException("MENTOR_SELECTION_STAGE_LOCKED", "当前阶段不能发布匹配结果", 409)
    result = db.query(MentorMatchResultVersion).filter_by(
        batch_id=batch.id, round=round
    ).order_by(MentorMatchResultVersion.version.desc()).first()
    if not result:
        raise AppException("MENTOR_SELECTION_RESULT_NOT_FOUND", "请先计算匹配结果", 409)
    MatchService.publish(db, result, batch)
    return {"success": True, "version": result.version, "status": result.status}


@router.get("/batches/{batch_id}/results/mine")
def my_result(batch_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    results = db.query(MentorMatchResultVersion).filter_by(
        batch_id=batch_id, status="published"
    ).order_by(MentorMatchResultVersion.id.desc()).all()
    if current_user.is_teacher:
        seen: set[int] = set()
        students = []
        for result in results:
            items = db.query(MentorMatchResultItem).filter_by(
                result_version_id=result.id, teacher_id=current_user.id, status="matched"
            ).all()
            for item in items:
                if item.student_id in seen:
                    continue
                seen.add(item.student_id)
                student = db.query(User).filter(User.id == item.student_id).first()
                if student:
                    students.append({
                        "id": student.id, "name": student.name, "student_no": student.student_no,
                    })
        return {"status": "published", "students": students}
    for result in results:
        student_result = db.query(MentorMatchResultItem).filter_by(
            result_version_id=result.id, student_id=current_user.id
        ).first()
        if student_result:
            teacher = (
                db.query(User).filter(User.id == student_result.teacher_id).first()
                if student_result.teacher_id else None
            )
            directions = []
            if teacher:
                directions = [{
                    "id": direction.id,
                    "title": direction.title,
                    "description": direction.description,
                    "tags": direction.tags,
                } for direction in db.query(TeacherDirection).filter(
                    TeacherDirection.teacher_id == teacher.id,
                    TeacherDirection.deleted_at.is_(None),
                    TeacherDirection.is_active.is_(True),
                ).order_by(TeacherDirection.id).all()]
            return {
                "round": result.round, "status": student_result.status,
                "teacher": {
                    "id": teacher.id, "name": teacher.name, "student_no": teacher.student_no,
                    "profile": teacher.profile, "directions": directions,
                } if teacher else None,
            }
    return None


@router.get("/batches/{batch_id}/summary")
def summary(batch_id: int, current_user=Depends(require_admin), db: Session = Depends(get_db)):
    batch = _batch_or_404(db, batch_id)
    result = db.query(MentorMatchResultVersion).filter_by(
        batch_id=batch.id
    ).order_by(MentorMatchResultVersion.id.desc()).first()
    items = db.query(MentorMatchResultItem).filter_by(
        result_version_id=result.id
    ).all() if result else []
    return {
        "batch": _batch_dict(batch), "matched": sum(item.status == "matched" for item in items),
        "unmatched": sum(item.status == "unmatched" for item in items),
        "results": [{
            "student_id": item.student_id, "teacher_id": item.teacher_id,
            "status": item.status, "matched_rank": item.matched_rank,
        } for item in items],
    }


@router.get("/batches/{batch_id}/export")
def export_batch(
    batch_id: int, dataset: str = Query("results"), format: str = Query("csv"),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    batch = _batch_or_404(db, batch_id)
    if dataset not in {"students", "results"} or format not in {"csv", "xlsx", "xls"}:
        raise AppException("MENTOR_SELECTION_EXPORT_INVALID", "导出数据集或格式不受支持", 400)
    rows: list[list] = []
    if dataset == "students":
        rows = [["student_no", "name", "class_name", "status"]]
        rows.extend([
            [
                student_row.student_no_snapshot, student_row.name_snapshot,
                student_row.class_name, student_row.status,
            ]
            for student_row in db.query(MentorSelectionBatchStudent).filter_by(batch_id=batch.id).all()
        ])
    else:
        rows = [["student_id", "teacher_id", "status", "matched_rank"]]
        result = db.query(MentorMatchResultVersion).filter_by(
            batch_id=batch.id
        ).order_by(MentorMatchResultVersion.id.desc()).first()
        result_rows = db.query(MentorMatchResultItem).filter_by(
            result_version_id=result.id
        ).all() if result else []
        rows.extend([
            [
                result_item.student_id, result_item.teacher_id or "",
                result_item.status, result_item.matched_rank or "",
            ]
            for result_item in result_rows
        ])
    rows = [[_safe_cell(value) for value in row] for row in rows]
    payload, media_type = _encode_export(rows, format)
    return StreamingResponse(
        iter([payload]), media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="mentor-selection-{batch.id}.{format}"'},
    )


def _safe_cell(value):
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _encode_export(rows: list[list], format: str) -> tuple[bytes, str]:
    if format == "csv":
        csv_output = io.StringIO()
        csv.writer(csv_output).writerows(rows)
        return csv_output.getvalue().encode("utf-8-sig"), "text/csv"
    if format == "xlsx":
        try:
            from openpyxl import Workbook
        except ImportError as exc:
            raise AppException("MENTOR_SELECTION_EXCEL_UNAVAILABLE", "服务端未安装 XLSX 导出依赖", 503) from exc
        workbook = Workbook(write_only=True)
        sheet = workbook.create_sheet("导师双选")
        for row in rows:
            sheet.append(row)
        binary_output = io.BytesIO()
        workbook.save(binary_output)
        return binary_output.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    try:
        import xlwt
    except ImportError as exc:
        raise AppException("MENTOR_SELECTION_EXCEL_UNAVAILABLE", "服务端未安装 XLS 导出依赖", 503) from exc
    if len(rows) > 65536:
        raise AppException("MENTOR_SELECTION_XLS_LIMIT", "XLS 行数超限，请改用 CSV 或 XLSX", 400)
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet("导师双选")
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row):
            sheet.write(row_index, column_index, value)
    xls_output = io.BytesIO()
    workbook.save(xls_output)
    return xls_output.getvalue(), "application/vnd.ms-excel"
