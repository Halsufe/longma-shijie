from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, require_admin
from backend.app.core.database import get_db
from backend.app.core.errors import AppException
from backend.app.repositories.party_repo import PartyRepository
from backend.app.schemas.party import (
    PartyAchievementLinkRequest,
    PartyImportResult,
    PartyAttendanceAction,
    PartyActivityCreate,
    PartyActivityInfo,
    PartyActivityListResponse,
    PartyActivityCategory,
    PartyActivityStatusUpdate,
    PartyActivityStatus,
    PartyActivitySummary,
    PartyActivityUpdate,
    PartyActivityArchiveInfo,
    PartyArchiveListResponse,
    PartyExportRequest,
    PartyMemberArchiveInfo,
    PartyMaterialInfo,
    PartyMaterialListResponse,
    PartyMineResponse,
    PartyMemberListResponse,
    PartyProfileCreate,
    PartyProfileInfo,
    PartyProfileUpdate,
    PartyParticipantInfo,
    PartyStatusChange,
    PartyStatsResponse,
    PoliticalStatusApply,
    PoliticalStatusMineResponse,
    PoliticalStatusReviewAction,
    PoliticalStatusReviewInfo,
    PoliticalStatusReviewListResponse,
    PoliticalStatusRosterListResponse,
    PoliticalLearningMaterialCreate,
    PoliticalLearningMaterialUpdate,
    PoliticalLearningMaterialInfo,
    PoliticalLearningMaterialListResponse,
)
from backend.app.schemas.achievement import AchievementInfo
from backend.app.schemas.user import OperationResult
from backend.app.services.party_profile_service import PartyProfileService
from backend.app.services.party_activity_service import PartyActivityService
from backend.app.services.party_archive_service import PartyArchiveService
from backend.app.services.party_export_service import PartyExportService
from backend.app.services.party_stats_service import PartyStatsService
from backend.app.services.party_registration_service import PartyRegistrationService
from backend.app.services.party_achievement_link_service import (
    PartyAchievementLinkService,
)
from backend.app.services.party_political_status_service import (
    PartyPoliticalStatusService,
)
from backend.app.services.party_political_material_service import (
    PartyPoliticalMaterialService,
)


router = APIRouter()


@router.get(
    "/political-status/mine", response_model=PoliticalStatusMineResponse
)
async def get_my_political_status(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return PartyPoliticalStatusService.mine(db, current_user)


@router.post(
    "/political-status/mine", response_model=PoliticalStatusReviewInfo
)
async def apply_my_political_status(
    form: PoliticalStatusApply,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review = PartyPoliticalStatusService.apply(
        db,
        current_user,
        to_status=form.to_status,
        remark=form.remark,
    )
    return PartyPoliticalStatusService.serialize_review(db, review)


@router.get(
    "/political-status/reviews",
    response_model=PoliticalStatusReviewListResponse,
)
async def list_political_status_reviews(
    status: str | None = None,
    user_id: int | None = Query(default=None, gt=0),
    to_status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return PartyPoliticalStatusService.list_reviews(
        db,
        status=status,
        user_id=user_id,
        to_status=to_status,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/political-status/roster",
    response_model=PoliticalStatusRosterListResponse,
)
async def list_political_status_roster(
    q: str | None = None,
    political_status: str | None = None,
    class_name: str | None = None,
    grade: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return PartyPoliticalStatusService.list_roster(
        db,
        q=q,
        political_status=political_status,
        class_name=class_name,
        grade=grade,
        page=page,
        page_size=page_size,
    )


@router.put(
    "/political-status/reviews/{review_id}/approve",
    response_model=PoliticalStatusReviewInfo,
)
async def approve_political_status_review(
    review_id: int,
    form: PoliticalStatusReviewAction,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    review = PartyPoliticalStatusService.review(
        db,
        review_id,
        approve=True,
        operator=current_user,
        remark=form.remark,
    )
    return PartyPoliticalStatusService.serialize_review(db, review)


@router.put(
    "/political-status/reviews/{review_id}/reject",
    response_model=PoliticalStatusReviewInfo,
)
async def reject_political_status_review(
    review_id: int,
    form: PoliticalStatusReviewAction,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    review = PartyPoliticalStatusService.review(
        db,
        review_id,
        approve=False,
        operator=current_user,
        remark=form.remark,
    )
    return PartyPoliticalStatusService.serialize_review(db, review)


@router.get(
    "/learning-materials", response_model=PoliticalLearningMaterialListResponse
)
async def list_political_learning_materials(
    current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    items = PartyPoliticalMaterialService.visible(db, current_user)
    return {"total": len(items), "items": [PartyPoliticalMaterialService._serialize(item) for item in items]}


@router.post(
    "/learning-materials", response_model=PoliticalLearningMaterialInfo
)
async def create_political_learning_material(
    form: PoliticalLearningMaterialCreate,
    current_user=Depends(require_admin), db: Session = Depends(get_db),
):
    item = PartyPoliticalMaterialService.create(db, form.model_dump(), current_user.id)
    return PartyPoliticalMaterialService._serialize(item)


@router.put(
    "/learning-materials/{material_id}", response_model=PoliticalLearningMaterialInfo
)
async def update_political_learning_material(
    material_id: int, form: PoliticalLearningMaterialUpdate,
    current_user=Depends(require_admin), db: Session = Depends(get_db),
):
    item = PartyPoliticalMaterialService.update(
        db, material_id, form.model_dump(exclude_unset=True)
    )
    return PartyPoliticalMaterialService._serialize(item)


@router.delete("/learning-materials/{material_id}", response_model=OperationResult)
async def delete_political_learning_material(
    material_id: int, current_user=Depends(require_admin), db: Session = Depends(get_db)
):
    PartyPoliticalMaterialService.delete(db, material_id)
    return OperationResult(success=True, message="政治学习资料已删除")


@router.post(
    "/learning-materials/{material_id}/attachments",
    response_model=PoliticalLearningMaterialInfo,
)
async def upload_political_learning_material_attachment(
    material_id: int,
    file: UploadFile = File(...),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = PartyPoliticalMaterialService.upload_attachment(db, material_id, file)
    return PartyPoliticalMaterialService._serialize(item)


@router.get("/learning-materials/{material_id}/attachments/{file_id}")
async def download_political_learning_material_attachment(
    material_id: int,
    file_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    path, attachment = PartyPoliticalMaterialService.get_attachment_for_download(
        db, material_id, file_id, current_user
    )
    return FileResponse(
        path=path,
        filename=str(attachment.get("original_name") or file_id),
        media_type=str(attachment.get("mime_type") or "application/octet-stream"),
        content_disposition_type="attachment",
    )


@router.post("/achievements/link", response_model=AchievementInfo)
async def link_party_achievement(
    form: PartyAchievementLinkRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return PartyAchievementLinkService.link(
        db,
        actor=current_user,
        link_type=form.link_type,
        activity_id=form.activity_id,
        target_user_id=form.user_id,
        achievement_category=form.achievement_category,
    )


@router.get("/mine", response_model=PartyMineResponse)
async def get_my_party_records(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return PartyRegistrationService.mine(db, current_user)


@router.get("/members", response_model=PartyMemberListResponse)
async def list_party_members(
    class_name: str | None = None,
    party_type: str | None = None,
    apply_status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    members, total, normalized_page, normalized_size = PartyRepository.list_members(
        db,
        class_name=class_name,
        party_type=party_type,
        apply_status=apply_status,
        page=page,
        page_size=page_size,
    )
    return {
        "total": total,
        "page": normalized_page,
        "page_size": normalized_size,
        "items": [PartyProfileService.serialize_member(user) for user in members],
    }


@router.post("/members", response_model=PartyProfileInfo)
async def create_party_member(
    form: PartyProfileCreate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = PartyProfileService.create_member(db, form.model_dump())
    return PartyProfileService.serialize_member(user)


@router.post("/members/import", response_model=PartyImportResult)
async def import_party_members(
    file: UploadFile = File(...),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    filename = (file.filename or "").lower()
    if not filename.endswith(".csv"):
        raise AppException("PARTY_CSV_INVALID", "批量导入仅支持 CSV 文件", 400)
    return PartyProfileService.import_csv(db, await file.read())


@router.put("/members/{user_id}", response_model=PartyProfileInfo)
async def update_party_member(
    user_id: int,
    form: PartyProfileUpdate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = PartyProfileService.update_member(
        db, user_id, form.model_dump(exclude_unset=True)
    )
    return PartyProfileService.serialize_member(user)


@router.delete("/members/{user_id}", response_model=OperationResult)
async def delete_party_member(
    user_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    PartyProfileService.delete_member(db, user_id)
    return OperationResult(success=True, message="党员档案已删除")


@router.put("/members/{user_id}/status", response_model=PartyProfileInfo)
async def change_party_member_status(
    user_id: int,
    form: PartyStatusChange,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = PartyProfileService.change_status(
        db,
        user_id,
        form.model_dump(by_alias=False),
        current_user,
    )
    return PartyProfileService.serialize_member(user)


@router.post("/materials", response_model=PartyMaterialInfo)
async def upload_party_material(
    user_id: int = Form(...),
    material_type: str = Form(...),
    title: str = Form(...),
    file: UploadFile = File(...),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return PartyProfileService.upload_material(
        db,
        user_id=user_id,
        material_type=material_type,
        title=title,
        file=file,
        uploaded_by=current_user.id,
    )


@router.get(
    "/members/{user_id}/materials",
    response_model=PartyMaterialListResponse,
)
async def list_party_materials(
    user_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    PartyProfileService.get_member_or_404(db, user_id)
    items = PartyRepository.list_materials(db, user_id)
    return {"total": len(items), "items": items}


@router.delete("/materials/{material_id}", response_model=OperationResult)
async def delete_party_material(
    material_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    PartyProfileService.delete_material(db, material_id)
    return OperationResult(success=True, message="党员发展材料已删除")


@router.get("/archives", response_model=PartyArchiveListResponse)
async def list_party_archives(
    year: int | None = Query(default=None, ge=1900, le=9999),
    category: PartyActivityCategory | None = None,
    class_name: str | None = None,
    grade: str | None = None,
    party_type: str | None = None,
    apply_status: str | None = None,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return PartyArchiveService.list_archives(
        db,
        year=year,
        category=category,
        class_name=class_name,
        grade=grade,
        party_type=party_type,
        apply_status=apply_status,
    )


@router.get(
    "/members/{user_id}/archive", response_model=PartyMemberArchiveInfo
)
async def get_party_member_archive(
    user_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return PartyArchiveService.member_archive(db, user_id)


@router.post("/stats/export")
async def export_party_stats(
    form: PartyExportRequest,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    filename, content = PartyExportService.export(db, **form.model_dump())
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/stats", response_model=PartyStatsResponse)
async def get_party_stats(
    stats_type: str | None = Query(default=None, alias="type"),
    class_name: str | None = None,
    grade: str | None = None,
    year: int | None = Query(default=None, ge=1900, le=9999),
    category: PartyActivityCategory | None = None,
    political_status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    allowed_types = {
        "member_counts",
        "participation",
        "materials",
        "development",
        "political_counts",
        "league_participation",
        "political_materials",
    }
    if stats_type is not None and stats_type not in allowed_types:
        raise AppException("PARTY_STATS_TYPE_INVALID", "不支持的党建统计类型", 422)
    return PartyStatsService.build(
        db,
        class_name=class_name,
        grade=grade,
        year=year,
        category=category,
        political_status_filter=political_status,
        page=page,
        page_size=page_size,
    )


@router.get("/activities", response_model=PartyActivityListResponse)
async def list_party_activities(
    status: PartyActivityStatus | None = None,
    category: PartyActivityCategory | None = None,
    year: int | None = Query(default=None, ge=1900, le=9999),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items, total, normalized_page, normalized_size = PartyActivityService.list_visible(
        db,
        current_user,
        status=status,
        category=category,
        year=year,
        page=page,
        page_size=page_size,
    )
    return {
        "total": total,
        "page": normalized_page,
        "page_size": normalized_size,
        "items": [
            PartyActivityService.serialize_for_user(db, item, current_user)
            for item in items
        ],
    }


@router.post("/activities", response_model=PartyActivityInfo)
async def create_party_activity(
    form: PartyActivityCreate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    activity = PartyActivityService.create(
        db, form.model_dump(), created_by=current_user.id
    )
    return PartyActivityService.serialize_for_user(db, activity, current_user)


@router.get("/activities/{activity_id}", response_model=PartyActivityInfo)
async def get_party_activity(
    activity_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    activity = PartyActivityService.visible_or_404(db, activity_id, current_user)
    return PartyActivityService.serialize_for_user(db, activity, current_user)


@router.put("/activities/{activity_id}", response_model=PartyActivityInfo)
async def update_party_activity(
    activity_id: int,
    form: PartyActivityUpdate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    activity = PartyActivityService.update(
        db, activity_id, form.model_dump(exclude_unset=True)
    )
    return PartyActivityService.serialize(activity)


@router.post("/activities/{activity_id}/publish", response_model=PartyActivityInfo)
async def publish_party_activity(
    activity_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    activity = PartyActivityService.transition(db, activity_id, "published")
    return PartyActivityService.serialize(activity)


@router.put("/activities/{activity_id}/status", response_model=PartyActivityInfo)
async def update_party_activity_status(
    activity_id: int,
    form: PartyActivityStatusUpdate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    activity = PartyActivityService.transition(db, activity_id, form.status)
    return PartyActivityService.serialize(activity)


@router.post("/activities/{activity_id}/summary", response_model=PartyActivityInfo)
async def update_party_activity_summary(
    activity_id: int,
    form: PartyActivitySummary,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    activity = PartyActivityService.update_summary(db, activity_id, form.model_dump())
    return PartyActivityService.serialize(activity)


@router.get(
    "/activities/{activity_id}/archive", response_model=PartyActivityArchiveInfo
)
async def get_party_activity_archive(
    activity_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return PartyArchiveService.activity_archive(db, activity_id)


@router.post("/activities/{activity_id}/materials", response_model=PartyActivityInfo)
async def upload_party_activity_material(
    activity_id: int,
    file: UploadFile = File(...),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    activity = PartyActivityService.upload_material(db, activity_id, file)
    return PartyActivityService.serialize(activity)


@router.delete("/activities/{activity_id}", response_model=OperationResult)
async def delete_party_activity(
    activity_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    PartyActivityService.delete(db, activity_id)
    return OperationResult(success=True, message="党建活动已删除")


@router.post(
    "/activities/{activity_id}/register", response_model=PartyParticipantInfo
)
async def register_party_activity(
    activity_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    participant = PartyRegistrationService.register(db, activity_id, current_user)
    return PartyRegistrationService.serialize(participant)


@router.delete(
    "/activities/{activity_id}/register", response_model=PartyParticipantInfo
)
async def cancel_party_activity_registration(
    activity_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    participant = PartyRegistrationService.cancel(db, activity_id, current_user)
    return PartyRegistrationService.serialize(participant)


@router.post(
    "/activities/{activity_id}/sign-in", response_model=PartyParticipantInfo
)
async def sign_in_party_activity(
    activity_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    participant = PartyRegistrationService.sign_in(db, activity_id, current_user)
    return PartyRegistrationService.serialize(participant)


@router.put(
    "/activities/{activity_id}/participants/{user_id}/attendance",
    response_model=PartyParticipantInfo,
)
async def update_party_activity_attendance(
    activity_id: int,
    user_id: int,
    form: PartyAttendanceAction,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    participant = PartyRegistrationService.set_attendance(
        db, activity_id, user_id, form.attendance_status
    )
    return PartyRegistrationService.serialize(participant)
