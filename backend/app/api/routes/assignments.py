import logging
from typing import cast

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.errors import AppException
from backend.app.repositories.school_repo import (
    AssignmentRepository,
    SubmissionRepository,
    CourseRepository,
)
from backend.app.repositories.user_repo import UserRepository
from backend.app.schemas.school import (
    AssignmentCreate,
    AssignmentUpdate,
    AssignmentInfo,
    AssignmentListResponse,
    SubmissionCreate,
    SubmissionInfo,
    SubmissionGrade,
    SubmissionVersionInfo,
    AssignmentStats,
)
from backend.app.api.deps import get_current_user, require_admin
from backend.app.services.submission_service import SubmissionService
from backend.app.services.notification_service import NotificationService
from backend.app.services.attachment_service import AttachmentService
from backend.app.services.file_preview_service import FilePreviewService
from backend.app.models.school import AssignmentAttachment, Submission, SubmissionAttachment

logger = logging.getLogger(__name__)
router = APIRouter()


def _assignment_or_404(db: Session, assignment_id: int, is_admin: bool):
    assignment = AssignmentRepository.get_by_id(db, assignment_id)
    if not assignment or (assignment.status != "published" and not is_admin):
        raise AppException("ASSIGNMENT_NOT_FOUND", "作业不存在", 404)
    return assignment


@router.post("/assignments/{assignment_id}/attachments")
async def upload_assignment_attachments(
    assignment_id: int, files: list[UploadFile] = File(...), current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    assignment = _assignment_or_404(db, assignment_id, True)
    return [AttachmentService.serialize(item) for item in AttachmentService.upload_assignment(db, assignment, files, current_user.id)]


@router.get("/assignments/{assignment_id}/attachments")
async def list_assignment_attachments(
    assignment_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db),
):
    _assignment_or_404(db, assignment_id, current_user.role == "admin")
    items = db.query(AssignmentAttachment).filter(
        AssignmentAttachment.assignment_id == assignment_id, AssignmentAttachment.deleted_at.is_(None)
    ).all()
    return [AttachmentService.serialize(item) for item in items]


@router.delete("/assignments/attachments/{attachment_id}")
async def delete_assignment_attachment(
    attachment_id: int, current_user=Depends(require_admin), db: Session = Depends(get_db),
):
    item = db.query(AssignmentAttachment).filter(AssignmentAttachment.id == attachment_id, AssignmentAttachment.deleted_at.is_(None)).first()
    if not item:
        raise AppException("ATTACHMENT_NOT_FOUND", "附件不存在", 404)
    item.deleted_at = __import__("backend.app.core.database", fromlist=["local_now"]).local_now()
    db.commit()
    return {"message": "附件已删除"}


@router.get("/assignments/attachments/{attachment_id}/download")
@router.get("/assignments/attachments/{attachment_id}/preview")
async def assignment_attachment_file(
    attachment_id: int, request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db),
):
    item = db.query(AssignmentAttachment).filter(AssignmentAttachment.id == attachment_id, AssignmentAttachment.deleted_at.is_(None)).first()
    if not item:
        raise AppException("ATTACHMENT_NOT_FOUND", "附件不存在", 404)
    _assignment_or_404(db, item.assignment_id, current_user.role == "admin")
    path = AttachmentService.path(item)
    if request.url.path.endswith("/preview"):
        result = FilePreviewService.preview(path=path, original_name=item.original_name, stored_name=item.stored_name, mime_type=item.mime_type, size=item.size, scope="assignment", user_id=item.uploaded_by)
        if result.get("format") == "html":
            return HTMLResponse(result.get("content") or "", media_type="text/html")
        if result.get("format") == "inline":
            preview_path = result.get("preview_url") or path
            return FileResponse(preview_path, filename=item.original_name, media_type=result.get("mime_type") or item.mime_type, headers={"Content-Disposition": f"inline; filename*=UTF-8''{item.original_name}"})
        return {"supported": False, "message": result.get("message", "暂不支持预览，请下载查看")}
    return FileResponse(path, filename=item.original_name, media_type=item.mime_type)


# ========== 管理员：作业 CRUD ==========
@router.post("/assignments", response_model=AssignmentInfo)
async def create_assignment(
    form: AssignmentCreate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    course = CourseRepository.get_by_id(db, form.course_id)
    if not course:
        raise AppException("COURSE_NOT_FOUND", "课程不存在", 404)
    a = AssignmentRepository.create(
        db, created_by=current_user.id,
        course_id=form.course_id, title=form.title, description=form.description,
        due_at=form.due_at, total_score=form.total_score, attachment_url=form.attachment_url,
        status="draft",
    )
    return AssignmentInfo.model_validate(a)


@router.get("/assignments", response_model=AssignmentListResponse)
async def list_assignments(
    course_id: int = Query(None),
    status: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 普通用户只能看 published；管理员可看全部
    if current_user.role != "admin" and status != "published":
        status = "published"
    items, total = AssignmentRepository.list(
        db, course_id=course_id, status=status, page=page, page_size=page_size
    )
    return AssignmentListResponse(total=total, items=[AssignmentInfo.model_validate(a) for a in items])


@router.get("/assignments/{assignment_id}", response_model=AssignmentInfo)
async def get_assignment(
    assignment_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    a = AssignmentRepository.get_by_id(db, assignment_id)
    if not a:
        raise AppException("ASSIGNMENT_NOT_FOUND", "作业不存在", 404)
    if a.status != "published" and current_user.role != "admin":
        raise AppException("ASSIGNMENT_NOT_FOUND", "作业不存在", 404)
    return AssignmentInfo.model_validate(a)


@router.put("/assignments/{assignment_id}", response_model=AssignmentInfo)
async def update_assignment(
    assignment_id: int,
    form: AssignmentUpdate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    a = AssignmentRepository.get_by_id(db, assignment_id)
    if not a:
        raise AppException("ASSIGNMENT_NOT_FOUND", "作业不存在", 404)
    a = AssignmentRepository.update(
        db, a,
        title=form.title, description=form.description, due_at=form.due_at,
        total_score=form.total_score, attachment_url=form.attachment_url,
    )
    return AssignmentInfo.model_validate(a)


@router.delete("/assignments/{assignment_id}")
async def delete_assignment(
    assignment_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    a = AssignmentRepository.get_by_id(db, assignment_id)
    if not a:
        raise AppException("ASSIGNMENT_NOT_FOUND", "作业不存在", 404)
    AssignmentRepository.soft_delete(db, a)
    return {"message": "作业已删除"}


@router.post("/assignments/{assignment_id}/publish", response_model=AssignmentInfo)
async def publish_assignment(
    assignment_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """发布作业并通知所有学生（幂等）"""
    a = AssignmentRepository.get_by_id(db, assignment_id)
    if not a:
        raise AppException("ASSIGNMENT_NOT_FOUND", "作业不存在", 404)
    a = AssignmentRepository.update(db, a, status="published")

    # 通知（幂等）
    course = CourseRepository.get_by_id(db, a.course_id)
    course_name = course.name if course else ""
    NotificationService.notify_new_assignment(db, a.id, a.title, course_name)

    return AssignmentInfo.model_validate(a)


@router.post("/assignments/{assignment_id}/withdraw", response_model=AssignmentInfo)
async def withdraw_assignment(
    assignment_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    a = AssignmentRepository.get_by_id(db, assignment_id)
    if not a:
        raise AppException("ASSIGNMENT_NOT_FOUND", "作业不存在", 404)
    a = AssignmentRepository.update(db, a, status="withdrawn")
    return AssignmentInfo.model_validate(a)


# ========== 学生：提交 ==========
@router.post("/assignments/{assignment_id}/submit")
async def submit_assignment(
    assignment_id: int,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """提交作业（截止前可更新，保留版本历史）"""
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        data = await request.form()
        content = str(data.get("content") or "")
        files = cast(list[UploadFile], [item for item in data.getlist("files") if hasattr(item, "filename") and hasattr(item, "file")])
        result = SubmissionService.submit(db, assignment_id, current_user.id, content)
        submission = db.query(Submission).filter(Submission.id == result["submission_id"]).first()
        if submission is None:
            raise AppException("SUBMISSION_NOT_FOUND", "提交不存在", 404)
        attachments = AttachmentService.upload_submission(db, submission, result["version"], files, current_user.id) if files else []
        return {**result, "attachments": [AttachmentService.serialize(item) for item in attachments]}
    form = SubmissionCreate.model_validate(await request.json())
    return SubmissionService.submit(db, assignment_id, current_user.id, form.content, form.attachment_name)


@router.post("/assignments/{assignment_id}/submit-files")
async def submit_assignment_files(
    assignment_id: int, content: str = Form(""), files: list[UploadFile] = File(default=[]),
    current_user=Depends(get_current_user), db: Session = Depends(get_db),
):
    if current_user.role not in ("student", "alumni"):
        raise AppException("FORBIDDEN", "当前身份不能提交作业", 403)
    result = SubmissionService.submit(db, assignment_id, current_user.id, content)
    submission = db.query(Submission).filter(Submission.id == result["submission_id"]).first()
    if submission is None:
        raise AppException("SUBMISSION_NOT_FOUND", "提交不存在", 404)
    attachments = AttachmentService.upload_submission(db, submission, result["version"], files, current_user.id) if files else []
    return {**result, "attachments": [AttachmentService.serialize(item) for item in attachments]}


@router.get("/submissions/{submission_id}/attachments")
async def list_submission_attachments(
    submission_id: int, version: int | None = Query(None), current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise AppException("SUBMISSION_NOT_FOUND", "提交不存在", 404)
    if current_user.role != "admin" and submission.user_id != current_user.id:
        raise AppException("FORBIDDEN", "无权查看他人提交附件", 403)
    query = db.query(SubmissionAttachment).filter(SubmissionAttachment.submission_id == submission_id)
    if version is not None:
        query = query.filter(SubmissionAttachment.version == version)
    return [AttachmentService.serialize(item) for item in query.order_by(SubmissionAttachment.version.desc()).all()]


@router.get("/submissions/attachments/{attachment_id}/download")
@router.get("/submissions/attachments/{attachment_id}/preview")
async def submission_attachment_file(
    attachment_id: int, request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db),
):
    item = db.query(SubmissionAttachment).filter(SubmissionAttachment.id == attachment_id).first()
    if not item:
        raise AppException("ATTACHMENT_NOT_FOUND", "附件不存在", 404)
    submission = db.query(Submission).filter(Submission.id == item.submission_id).first()
    if not submission or (current_user.role != "admin" and submission.user_id != current_user.id):
        raise AppException("FORBIDDEN", "无权访问附件", 403)
    path = AttachmentService.path(item)
    if request.url.path.endswith("/preview"):
        result = FilePreviewService.preview(path=path, original_name=item.original_name, stored_name=item.stored_name, mime_type=item.mime_type, size=item.size, scope="submission", user_id=item.uploaded_by, version=item.version)
        if result.get("format") == "html":
            return HTMLResponse(result.get("content") or "", media_type="text/html")
        if result.get("format") == "inline":
            preview_path = result.get("preview_url") or path
            return FileResponse(preview_path, filename=item.original_name, media_type=result.get("mime_type") or item.mime_type, headers={"Content-Disposition": f"inline; filename*=UTF-8''{item.original_name}"})
        return {"supported": False, "message": result.get("message", "暂不支持预览，请下载查看")}
    return FileResponse(path, filename=item.original_name, media_type=item.mime_type)


@router.get("/assignments/{assignment_id}/submission", response_model=SubmissionInfo)
async def get_my_submission(
    assignment_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = SubmissionRepository.get_by_assignment_and_user(db, assignment_id, current_user.id)
    if not sub:
        raise AppException("SUBMISSION_NOT_FOUND", "尚未提交", 404)
    return SubmissionInfo.model_validate(sub)


# ========== 管理员：批改 + 统计 ==========
@router.get("/assignments/{assignment_id}/submissions", response_model=list[SubmissionInfo])
async def list_submissions(
    assignment_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    a = AssignmentRepository.get_by_id(db, assignment_id)
    if not a:
        raise AppException("ASSIGNMENT_NOT_FOUND", "作业不存在", 404)
    items = SubmissionRepository.list_by_assignment(db, assignment_id)
    return [SubmissionInfo.model_validate(s) for s in items]


@router.get("/assignments/{assignment_id}/stats", response_model=AssignmentStats)
async def assignment_stats(
    assignment_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """作业统计：提交人数/未交名单"""
    a = AssignmentRepository.get_by_id(db, assignment_id)
    if not a:
        raise AppException("ASSIGNMENT_NOT_FOUND", "作业不存在", 404)

    subs = SubmissionRepository.list_by_assignment(db, assignment_id)
    submitted_user_ids = {s.user_id for s in subs}
    graded_count = sum(1 for s in subs if s.status == "graded")

    students = UserRepository.list_active_students(db)
    not_submitted = [
        {"user_id": s.id, "name": s.name, "student_no": s.student_no}
        for s in students if s.id not in submitted_user_ids
    ]
    return AssignmentStats(
        assignment_id=assignment_id,
        title=a.title,
        total_students=len(students),
        submitted_count=len(subs),
        graded_count=graded_count,
        not_submitted=not_submitted,
    )


@router.post("/submissions/{submission_id}/grade")
async def grade_submission(
    submission_id: int,
    form: SubmissionGrade,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return SubmissionService.grade(db, submission_id, form.score, form.feedback)


@router.get("/submissions/{submission_id}/versions", response_model=list[SubmissionVersionInfo])
async def list_submission_versions(
    submission_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    is_admin = current_user.role == "admin"
    items = SubmissionService.get_versions(db, submission_id, current_user.id, is_admin)
    return [SubmissionVersionInfo.model_validate(v) for v in items]
