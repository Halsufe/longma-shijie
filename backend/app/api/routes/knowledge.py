import logging

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.errors import AppException
from backend.app.core.config import settings
from backend.app.repositories.file_repo import FileRepository
from backend.app.schemas.file import (
    FileInfo,
    FileListResponse,
    FileUpdate,
    QuotaInfo,
    FolderCreate,
    FolderInfo,
    FolderListResponse,
)
from backend.app.services.file_preview_adapter import FilePreviewAdapter
from backend.app.api.deps import get_current_user
from backend.app.services.file_service import FileService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload", response_model=FileInfo)
async def upload_file(
    file: UploadFile = File(...),
    tag: str = Form(None),
    folder_id: int = Form(None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上传文件到个人知识库"""
    try:
        folder = FileRepository.get_folder(db, folder_id) if folder_id else None
        if folder and (folder.scope != "personal" or folder.owner_user_id != current_user.id):
            raise AppException("FOLDER_NOT_FOUND", "文件夹不存在", 404)
        result = FileService.upload_and_parse(db, current_user.id, "personal", file, tag, folder_id)
        kf = FileRepository.get_by_id(db, result["id"])
        return FileInfo.model_validate(kf)
    except ValueError as e:
        raise AppException("UPLOAD_FAILED", str(e), 400)


@router.get("/files", response_model=FileListResponse)
async def list_files(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),  # 上限由 normalize_page_size 静默截断到 100
    q: str = Query(None),
    folder_id: int = Query(None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items, total = FileRepository.list_personal(db, current_user.id, page, page_size, q)
    if folder_id is not None:
        items = [item for item in items if item.folder_id == folder_id]
        total = len(items)
    return FileListResponse(total=total, items=[FileInfo.model_validate(f) for f in items])


@router.get("/files/{file_id}", response_model=FileInfo)
async def get_file(
    file_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kf = FileRepository.get_by_id(db, file_id)
    if not kf or kf.scope != "personal" or kf.owner_user_id != current_user.id:
        raise AppException("FILE_NOT_FOUND", "文件不存在", 404)
    return FileInfo.model_validate(kf)


@router.get("/folders", response_model=FolderListResponse)
async def list_folders(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return FolderListResponse(
        items=[FolderInfo.model_validate(x) for x in FileRepository.list_folders(db, "personal", current_user.id)]
    )


@router.post("/folders", response_model=FolderInfo)
async def create_folder(form: FolderCreate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return FileRepository.create_folder(db, "personal", current_user.id, current_user.id, form.name)
    except ValueError as exc:
        raise AppException("FOLDER_INVALID", str(exc), 400)


@router.put("/folders/{folder_id}", response_model=FolderInfo)
async def rename_folder(
    folder_id: int, form: FolderCreate, current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    folder = FileRepository.get_folder(db, folder_id)
    if not folder or folder.scope != "personal" or folder.owner_user_id != current_user.id:
        raise AppException("FOLDER_NOT_FOUND", "文件夹不存在", 404)
    try:
        return FileRepository.rename_folder(db, folder, form.name)
    except ValueError as exc:
        raise AppException("FOLDER_INVALID", str(exc), 400)


@router.delete("/folders/{folder_id}")
async def delete_folder(folder_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    folder = FileRepository.get_folder(db, folder_id)
    if not folder or folder.scope != "personal" or folder.owner_user_id != current_user.id:
        raise AppException("FOLDER_NOT_FOUND", "文件夹不存在", 404)
    try:
        FileRepository.delete_folder(db, folder)
    except ValueError as exc:
        raise AppException("FOLDER_NOT_EMPTY", str(exc), 400)
    return {"success": True}


@router.put("/files/{file_id}/move", response_model=FileInfo)
async def move_file(
    file_id: int, form: FileUpdate, current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    item = FileRepository.get_by_id(db, file_id)
    if not item or item.scope != "personal" or item.owner_user_id != current_user.id:
        raise AppException("FILE_NOT_FOUND", "文件不存在", 404)
    folder = FileRepository.get_folder(db, form.folder_id) if form.folder_id else None
    try:
        return FileRepository.move_file(db, item, folder)
    except ValueError as exc:
        raise AppException("MOVE_INVALID", str(exc), 400)


@router.get("/files/{file_id}/preview")
async def preview_file(file_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return FilePreviewAdapter.preview(db, file_id, current_user.id, "personal")
    except ValueError as exc:
        raise AppException("FILE_NOT_FOUND", str(exc), 404)


@router.get("/files/{file_id}/preview/raw")
async def preview_file_raw_legacy(file_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        path, media_type = FilePreviewAdapter.raw_path(db, file_id, current_user.id, "personal")
        return FileResponse(path=path, media_type=media_type, headers={"Content-Disposition": "inline"})
    except ValueError as exc:
        raise AppException("FILE_NOT_FOUND", str(exc), 404)


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        file_path, original_name = FileService.get_file_path_for_download(db, file_id, current_user.id)
        return FileResponse(
            path=file_path,
            filename=original_name,
            media_type="application/octet-stream",
        )
    except ValueError as e:
        raise AppException("FILE_NOT_FOUND", str(e), 404)


@router.put("/files/{file_id}", response_model=FileInfo)
async def update_file(
    file_id: int,
    form: FileUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kf = FileRepository.get_by_id(db, file_id)
    if not kf or kf.scope != "personal" or kf.owner_user_id != current_user.id:
        raise AppException("FILE_NOT_FOUND", "文件不存在", 404)
    kf = FileRepository.update(
        db,
        kf,
        original_name=form.original_name,
        tag=form.tag,
        folder_id=form.folder_id,
    )
    return FileInfo.model_validate(kf)


@router.delete("/files/{file_id}")
async def delete_file(
    file_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = FileService.delete_file(db, file_id, current_user.id, "personal")
        return result
    except ValueError as e:
        raise AppException("FILE_NOT_FOUND", str(e), 404)


@router.get("/quota", response_model=QuotaInfo)
async def get_quota(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    used = FileRepository.get_user_total_size(db, current_user.id)
    quota = settings.DEFAULT_QUOTA_MB * 1024 * 1024
    return QuotaInfo(
        used_bytes=used,
        quota_bytes=quota,
        used_mb=round(used / 1024 / 1024, 2),
        quota_mb=float(settings.DEFAULT_QUOTA_MB),
        percentage=round(used / quota * 100, 2) if quota > 0 else 0,
    )
