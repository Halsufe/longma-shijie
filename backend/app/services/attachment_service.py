import os
from collections.abc import Sequence

from fastapi import UploadFile
from sqlalchemy.orm import Session

from backend.app.core.database import local_now
from backend.app.core.errors import AppException
from backend.app.core.storage import StorageService
from backend.app.models.school import Assignment, AssignmentAttachment, Submission, SubmissionAttachment
from backend.app.ai.parser import ALLOWED_EXTENSIONS, is_allowed_extension


MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_BATCH_BYTES = 200 * 1024 * 1024
MAX_FILES = 10


def _file_size(file: UploadFile) -> int:
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    return size


def validate_files(files: Sequence[UploadFile]) -> None:
    if len(files) > MAX_FILES:
        raise AppException("TOO_MANY_FILES", "单次最多上传 10 个文件", 400)
    sizes = [_file_size(file) for file in files]
    for file in files:
        if not file.filename or not is_allowed_extension(file.filename):
            raise AppException("FILE_TYPE_NOT_ALLOWED", "附件类型不受支持", 400)
    if any(size > MAX_FILE_BYTES for size in sizes):
        raise AppException("FILE_TOO_LARGE", "单文件不能超过 50MB", 400)
    if sum(sizes) > MAX_BATCH_BYTES:
        raise AppException("BATCH_TOO_LARGE", "单次附件总大小不能超过 200MB", 400)
    for file in files:
        try:
            StorageService.validate_upload(
                file,
                max_bytes=MAX_FILE_BYTES,
                allowed_extensions=ALLOWED_EXTENSIONS,
            )
        except ValueError as exc:
            raise AppException(
                "FILE_SIGNATURE_INVALID",
                "文件内容与扩展名不匹配",
                400,
            ) from exc


class AttachmentService:
    @staticmethod
    def upload_assignment(db: Session, assignment: Assignment, files: Sequence[UploadFile], user_id: int) -> list[AssignmentAttachment]:
        validate_files(files)
        existing = db.query(AssignmentAttachment).filter(
            AssignmentAttachment.assignment_id == assignment.id,
            AssignmentAttachment.deleted_at.is_(None),
        ).all()
        if sum(item.size for item in existing) + sum(_file_size(file) for file in files) > MAX_BATCH_BYTES:
            raise AppException("ASSIGNMENT_ATTACHMENTS_TOO_LARGE", "单作业附件总大小不能超过 200MB", 400)
        result: list[AssignmentAttachment] = []
        for file in files:
            if not file.filename or not is_allowed_extension(file.filename):
                raise AppException("FILE_TYPE_NOT_ALLOWED", "附件类型不受支持", 400)
            stored_name, mime_type, size = StorageService.save_file("assignment", user_id, file)
            item = AssignmentAttachment(
                assignment_id=assignment.id, original_name=file.filename or stored_name,
                stored_name=stored_name, mime_type=mime_type, size=size, uploaded_by=user_id,
            )
            db.add(item)
            result.append(item)
        db.commit()
        for item in result:
            db.refresh(item)
        return result

    @staticmethod
    def upload_submission(db: Session, submission: Submission, version: int, files: Sequence[UploadFile], user_id: int) -> list[SubmissionAttachment]:
        validate_files(files)
        result = []
        for file in files:
            if not file.filename or not is_allowed_extension(file.filename):
                raise AppException("FILE_TYPE_NOT_ALLOWED", "附件类型不受支持", 400)
            stored_name, mime_type, size = StorageService.save_file("submission", user_id, file)
            item = SubmissionAttachment(
                submission_id=submission.id, version=version, original_name=file.filename or stored_name,
                stored_name=stored_name, mime_type=mime_type, size=size, uploaded_by=user_id,
            )
            db.add(item)
            result.append(item)
        db.commit()
        for item in result:
            db.refresh(item)
        return result

    @staticmethod
    def path(item: AssignmentAttachment | SubmissionAttachment) -> str:
        scope = "assignment" if isinstance(item, AssignmentAttachment) else "submission"
        path = StorageService.get_file_path(scope, item.uploaded_by, item.stored_name)
        if not os.path.isfile(path):
            raise AppException("ATTACHMENT_NOT_FOUND", "附件不存在", 404)
        return path

    @staticmethod
    def serialize(item: AssignmentAttachment | SubmissionAttachment) -> dict:
        data = {
            "id": item.id, "original_name": item.original_name, "mime_type": item.mime_type,
            "size": item.size, "created_at": item.created_at,
        }
        if isinstance(item, SubmissionAttachment):
            data["version"] = item.version
        return data
