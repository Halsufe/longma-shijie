import logging

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.errors import AppException
from backend.app.repositories.file_repo import FileRepository
from backend.app.schemas.file import (
    FileInfo,
    FileListResponse,
    FileUpdate,
    FolderCreate,
    FolderInfo,
    FolderListResponse,
    FileVersionInfo,
)
from backend.app.api.deps import get_current_user, require_admin
from backend.app.services.file_service import FileService
from backend.app.services.file_preview_adapter import FilePreviewAdapter
from backend.app.services.knowledge_version_service import KnowledgeVersionService
from backend.app.services.knowledge_scope import KnowledgeScopeGuard

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload", response_model=FileInfo)
async def upload_class_file(
    file: UploadFile = File(...),
    tag: str = Form(None),
    folder_id: int = Form(None),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """上传文件到班级知识库（仅管理员）"""
    try:
        folder = FileRepository.get_folder(db, folder_id) if folder_id else None
        if folder and (folder.scope != "class" or folder.owner_user_id != current_user.id):
            raise AppException("FOLDER_NOT_FOUND", "文件夹不存在", 404)
        try:
            context = KnowledgeScopeGuard.authorize(db, current_user, "class")
        except PermissionError as exc:
            raise AppException("KNOWLEDGE_SCOPE_FORBIDDEN", str(exc), 403) from exc
        result = FileService.upload_and_parse(
            db, current_user.id, "class", file, tag, folder_id, class_id=context.class_id
        )
        kf = FileRepository.get_by_id(db, result["id"])
        return FileInfo.model_validate(kf)
    except ValueError as e:
        raise AppException("UPLOAD_FAILED", str(e), 400)


@router.get("/files", response_model=FileListResponse)
async def list_class_files(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),  # 上限由 normalize_page_size 静默截断到 100
    q: str = Query(None),
    folder_id: int = Query(None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """所有登录用户可查看班级知识库"""
    try:
        context = KnowledgeScopeGuard.authorize(db, current_user, "class")
    except PermissionError as exc:
        raise AppException("KNOWLEDGE_SCOPE_FORBIDDEN", str(exc), 403) from exc
    items, total = FileRepository.list_class(db, page, page_size, q)
    items = [item for item in items if item.class_id is None or item.class_id == context.class_id]
    total = len(items)
    if folder_id is not None:
        items = [item for item in items if item.folder_id == folder_id]
        total = len(items)
    return FileListResponse(total=total, items=[FileInfo.model_validate(f) for f in items])


@router.get("/files/{file_id}", response_model=FileInfo)
async def get_class_file(
    file_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kf = FileRepository.get_by_id(db, file_id)
    try:
        context = KnowledgeScopeGuard.authorize(db, current_user, "class")
    except PermissionError as exc:
        raise AppException("KNOWLEDGE_SCOPE_FORBIDDEN", str(exc), 403) from exc
    if not kf or kf.scope != "class" or (kf.class_id is not None and kf.class_id != context.class_id):
        raise AppException("FILE_NOT_FOUND", "文件不存在", 404)
    return FileInfo.model_validate(kf)


@router.get("/folders", response_model=FolderListResponse)
async def list_folders(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    # class folders are owned by the creating admin; list all visible class folders
    from backend.app.models.file import KnowledgeFolder

    folders = (
        db.query(KnowledgeFolder)
        .filter(KnowledgeFolder.scope == "class", KnowledgeFolder.deleted_at.is_(None))
        .order_by(KnowledgeFolder.name)
        .all()
    )
    return FolderListResponse(items=[FolderInfo.model_validate(x) for x in folders])


@router.post("/folders", response_model=FolderInfo)
async def create_folder(form: FolderCreate, current_user=Depends(require_admin), db: Session = Depends(get_db)):
    try:
        return FileRepository.create_folder(db, "class", current_user.id, current_user.id, form.name)
    except ValueError as exc:
        raise AppException("FOLDER_INVALID", str(exc), 400)


@router.put("/folders/{folder_id}", response_model=FolderInfo)
async def rename_folder(
    folder_id: int, form: FolderCreate, current_user=Depends(require_admin), db: Session = Depends(get_db)
):
    folder = FileRepository.get_folder(db, folder_id)
    if not folder or folder.scope != "class":
        raise AppException("FOLDER_NOT_FOUND", "文件夹不存在", 404)
    try:
        return FileRepository.rename_folder(db, folder, form.name)
    except ValueError as exc:
        raise AppException("FOLDER_INVALID", str(exc), 400)


@router.delete("/folders/{folder_id}")
async def delete_folder(folder_id: int, current_user=Depends(require_admin), db: Session = Depends(get_db)):
    folder = FileRepository.get_folder(db, folder_id)
    if not folder or folder.scope != "class":
        raise AppException("FOLDER_NOT_FOUND", "文件夹不存在", 404)
    try:
        FileRepository.delete_folder(db, folder)
    except ValueError as exc:
        raise AppException("FOLDER_NOT_EMPTY", str(exc), 400)
    return {"success": True}


@router.get("/files/{file_id}/preview")
async def preview_class_file(file_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return FilePreviewAdapter.preview(db, file_id, current_user.id, "class")
    except ValueError as exc:
        raise AppException("FILE_NOT_FOUND", str(exc), 404)


@router.get("/files/{file_id}/preview/raw")
async def preview_class_file_raw_legacy(file_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        path, media_type = FilePreviewAdapter.raw_path(db, file_id, current_user.id, "class")
        return FileResponse(path=path, media_type=media_type, headers={"Content-Disposition": "inline"})
    except ValueError as exc:
        raise AppException("FILE_NOT_FOUND", str(exc), 404)


@router.put("/files/{file_id}/move", response_model=FileInfo)
async def move_class_file(
    file_id: int, form: FileUpdate, current_user=Depends(require_admin), db: Session = Depends(get_db)
):
    item = FileRepository.get_by_id(db, file_id)
    if not item or item.scope != "class":
        raise AppException("FILE_NOT_FOUND", "文件不存在", 404)
    folder = FileRepository.get_folder(db, form.folder_id) if form.folder_id else None
    if folder and folder.scope != "class":
        raise AppException("FOLDER_NOT_FOUND", "文件夹不存在", 404)
    item.folder_id = folder.id if folder else None
    db.commit()
    db.refresh(item)
    return item


@router.post("/files/{file_id}/replace", response_model=FileInfo)
async def replace_class_file(
    file_id: int, file: UploadFile = File(...), current_user=Depends(require_admin), db: Session = Depends(get_db)
):
    item = FileRepository.get_by_id(db, file_id)
    if not item or item.scope != "class":
        raise AppException("FILE_NOT_FOUND", "文件不存在", 404)
    try:
        return KnowledgeVersionService.replace(db, item, file, current_user.id)
    except ValueError as exc:
        raise AppException("VERSION_REPLACE_FAILED", str(exc), 400)


@router.get("/files/{file_id}/versions", response_model=list[FileVersionInfo])
async def list_file_versions(file_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    item = FileRepository.get_by_id(db, file_id)
    if not item or item.scope != "class":
        raise AppException("FILE_NOT_FOUND", "文件不存在", 404)
    return FileRepository.list_versions(db, file_id)


@router.get("/files/{file_id}/versions/{version}/download")
async def download_file_version(
    file_id: int, version: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    item = FileRepository.get_by_id(db, file_id)
    if not item or item.scope != "class":
        raise AppException("FILE_NOT_FOUND", "文件不存在", 404)
    history = next((x for x in FileRepository.list_versions(db, file_id) if x.version == version), None)
    if not history:
        raise AppException("VERSION_NOT_FOUND", "历史版本不存在", 404)
    from backend.app.core.storage import StorageService
    import os

    path = StorageService.get_file_path("class", item.owner_user_id, history.stored_name)
    if not os.path.exists(path):
        raise AppException("FILE_NOT_FOUND", "文件不存在", 404)
    return FileResponse(path=path, filename=history.original_name, media_type=history.mime_type)


@router.get("/files/{file_id}/download")
async def download_class_file(
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
async def update_class_file(
    file_id: int,
    form: FileUpdate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    kf = FileRepository.get_by_id(db, file_id)
    if not kf or kf.scope != "class":
        raise AppException("FILE_NOT_FOUND", "文件不存在", 404)
    kf = FileRepository.update(
        db,
        kf,
        original_name=form.original_name,
        tag=form.tag,
        is_pinned=form.is_pinned,
        folder_id=form.folder_id,
    )
    return FileInfo.model_validate(kf)


@router.delete("/files/{file_id}")
async def delete_class_file(
    file_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        result = FileService.delete_file(db, file_id, current_user.id, "class")
        return result
    except ValueError as e:
        raise AppException("FILE_NOT_FOUND", str(e), 404)
