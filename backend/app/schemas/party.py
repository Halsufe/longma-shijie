from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field


class PartyProfileFields(BaseModel):
    party_type: str
    branch_name: str = Field(default="大数据党支部", min_length=1, max_length=100)
    class_name: str = Field(min_length=1, max_length=100)
    grade: str = Field(min_length=1, max_length=20)
    apply_date: str
    activist_date: str | None = None
    target_date: str | None = None
    probation_date: str | None = None
    full_date: str | None = None
    party_join_date: str | None = None
    apply_status: str
    stop_reason: str | None = Field(default=None, max_length=500)
    introducer_names: str | None = Field(default=None, max_length=200)
    mentor_names: str | None = Field(default=None, max_length=200)
    remark: str | None = Field(default=None, max_length=2000)

    model_config = {"extra": "forbid"}


class PartyProfileCreate(PartyProfileFields):
    # Keep user_id for API compatibility; new callers can identify a student
    # by student_no, which is the value administrators normally know.
    user_id: int | None = Field(default=None, gt=0)
    student_no: str | None = Field(default=None, min_length=1, max_length=50)


class PartyProfileUpdate(BaseModel):
    party_type: str | None = None
    branch_name: str | None = Field(default=None, min_length=1, max_length=100)
    class_name: str | None = Field(default=None, min_length=1, max_length=100)
    grade: str | None = Field(default=None, min_length=1, max_length=20)
    apply_date: str | None = None
    activist_date: str | None = None
    target_date: str | None = None
    probation_date: str | None = None
    full_date: str | None = None
    party_join_date: str | None = None
    apply_status: str | None = None
    stop_reason: str | None = Field(default=None, max_length=500)
    introducer_names: str | None = Field(default=None, max_length=200)
    mentor_names: str | None = Field(default=None, max_length=200)
    remark: str | None = Field(default=None, max_length=2000)

    model_config = {"extra": "forbid"}


class PartyProfileInfo(PartyProfileFields):
    user_id: int
    student_no: str
    name: str
    party: dict
    deleted_at: str | None = None


class PartyMemberListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[PartyProfileInfo]


class PartyStatusChange(BaseModel):
    apply_status: str = Field(
        validation_alias=AliasChoices("apply_status", "status")
    )
    effective_date: str | None = Field(
        default=None,
        validation_alias=AliasChoices("effective_date", "status_date"),
    )
    stop_reason: str | None = Field(default=None, max_length=500)

    model_config = {"extra": "forbid", "populate_by_name": True}


class PartyImportError(BaseModel):
    row: int
    student_no: str | None = None
    field: str | None = None
    message: str


class PartyImportResult(BaseModel):
    total: int
    created: int
    added: int
    updated: int
    skipped: int
    error_count: int
    errors: list[PartyImportError]


class PartyMaterialInfo(BaseModel):
    id: int
    user_id: int
    material_type: str
    title: str
    original_name: str
    stored_name: str
    mime_type: str
    size: int
    uploaded_by: int
    uploaded_at: datetime
    deleted_at: datetime | None = None

    model_config = {"from_attributes": True}


class PartyMaterialListResponse(BaseModel):
    total: int
    items: list[PartyMaterialInfo]


PartyActivityCategory = Literal[
    "组织生活会",
    "主题党日",
    "理论学习",
    "志愿公益",
    "发展工作",
    "民主评议",
    "专题教育",
    "其他",
    "主题团日",
    "团学实践",
    "团组织建设",
    "其他团学",
]
PartyActivityTarget = Literal[
    "全体党员",
    "党员与积极分子",
    "预备党员与积极分子",
    "全体团员",
    "党员与团员",
    "全体学生",
    "群众",
    "指定人员",
]
PartyActivityStatus = Literal[
    "draft",
    "published",
    "ongoing",
    "finished",
    "archived",
]
PartyRegistrationStatus = Literal["registered", "cancelled"]
PartyAttendanceStatus = Literal["none", "signed_in", "absent"]
PartySignInMethod = Literal["manual", "self", "qr", "location"]


class PartyActivityCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    category: PartyActivityCategory
    content: str = Field(min_length=1)
    location: str = Field(min_length=1, max_length=200)
    start_at: datetime
    end_at: datetime
    registration_deadline: datetime | None = None
    target_roles: PartyActivityTarget
    target_member_ids: list[int] = Field(
        default_factory=list,
        validation_alias=AliasChoices("target_member_ids", "target_member_ids_json"),
    )
    max_participants: int | None = Field(default=None, gt=0)
    materials: list[dict[str, Any]] = Field(
        default_factory=list,
        validation_alias=AliasChoices("materials", "materials_json"),
    )

    model_config = {"extra": "forbid", "populate_by_name": True}


class PartyActivityUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    category: PartyActivityCategory | None = None
    content: str | None = Field(default=None, min_length=1)
    location: str | None = Field(default=None, min_length=1, max_length=200)
    start_at: datetime | None = None
    end_at: datetime | None = None
    registration_deadline: datetime | None = None
    target_roles: PartyActivityTarget | None = None
    target_member_ids: list[int] | None = Field(
        default=None,
        validation_alias=AliasChoices("target_member_ids", "target_member_ids_json"),
    )
    max_participants: int | None = Field(default=None, gt=0)
    materials: list[dict[str, Any]] | None = Field(
        default=None,
        validation_alias=AliasChoices("materials", "materials_json"),
    )
    summary: str | None = None
    summary_attachments: list[dict[str, Any]] | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "summary_attachments", "summary_attachments_json"
        ),
    )

    model_config = {"extra": "forbid", "populate_by_name": True}


class PartyActivitySummary(BaseModel):
    summary: str = Field(min_length=1)
    summary_attachments: list[dict[str, Any]] = Field(
        default_factory=list,
        validation_alias=AliasChoices(
            "summary_attachments", "summary_attachments_json"
        ),
    )
    archive: bool = False

    model_config = {"extra": "forbid", "populate_by_name": True}


class PartyActivityStatusUpdate(BaseModel):
    status: PartyActivityStatus

    model_config = {"extra": "forbid"}


class PartyActivityInfo(BaseModel):
    id: int
    title: str
    category: PartyActivityCategory
    content: str
    location: str
    start_at: datetime
    end_at: datetime
    registration_deadline: datetime | None
    target_roles: PartyActivityTarget
    target_member_ids: list[int]
    target_member_ids_json: list[int]
    max_participants: int | None
    materials: list[dict[str, Any]]
    materials_json: list[dict[str, Any]]
    summary: str | None
    summary_attachments: list[dict[str, Any]]
    summary_attachments_json: list[dict[str, Any]]
    status: PartyActivityStatus
    created_by: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    participant: "PartyParticipantInfo | None" = None
    my_participation: "PartyParticipantInfo | None" = None


class PartyActivityListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[PartyActivityInfo]


class PartyAttendanceAction(BaseModel):
    attendance_status: Literal["signed_in", "absent"]

    model_config = {"extra": "forbid"}


class PartyParticipantInfo(BaseModel):
    id: int
    activity_id: int
    user_id: int
    registration_status: PartyRegistrationStatus
    attendance_status: PartyAttendanceStatus
    sign_in_time: datetime | None
    sign_in_method: PartySignInMethod | None
    created_at: datetime
    updated_at: datetime


class PartyParticipationRecord(PartyParticipantInfo):
    activity: PartyActivityInfo
    title: str
    category: PartyActivityCategory
    start_at: datetime
    end_at: datetime
    location: str


class PartyArchiveUser(BaseModel):
    user_id: int
    student_no: str
    name: str
    role: str
    party: dict[str, Any] = Field(default_factory=dict)


class PartyArchiveParticipant(PartyParticipantInfo):
    user: PartyArchiveUser


class PartyActivityArchiveInfo(BaseModel):
    activity: PartyActivityInfo
    expected_members: list[PartyArchiveUser]
    expected_member_ids: list[int]
    participants: list[PartyArchiveParticipant]
    expected_count: int
    registered_count: int
    signed_in_count: int
    absent_count: int


class PartyTimelineEntry(BaseModel):
    key: str
    label: str
    date: str


class PartyMemberArchiveInfo(BaseModel):
    member: PartyProfileInfo
    timeline: list[PartyTimelineEntry]
    materials: list[PartyMaterialInfo]


class PartyArchiveListResponse(BaseModel):
    activities: list[PartyActivityInfo]
    members: list[PartyProfileInfo]
    activity_total: int
    member_total: int


class PartyStatsGroupItem(BaseModel):
    key: str
    label: str
    count: int


class PartyMemberCountsStats(BaseModel):
    total: int
    by_party_type: list[PartyStatsGroupItem]
    by_class: list[PartyStatsGroupItem]
    by_grade: list[PartyStatsGroupItem]


class PartyActivityParticipationStats(BaseModel):
    activity_id: int
    title: str
    expected_count: int
    registered_count: int
    signed_in_count: int
    participation_rate: float
    registration_rate: float


class PartyParticipationStats(BaseModel):
    expected_count: int
    registered_count: int
    signed_in_count: int
    expected: int
    registered: int
    signed_in: int
    participation_rate: float
    registration_rate: float
    activities: list[PartyActivityParticipationStats]
    total: int
    page: int
    page_size: int


class PartyMaterialsStats(BaseModel):
    total: int
    activity_materials: int
    member_materials: int
    learning_materials: int
    development_materials: int
    by_month: list[PartyStatsGroupItem]
    by_activity: list[dict[str, Any]]
    by_member: list[dict[str, Any]]


class PartyDevelopmentStats(BaseModel):
    by_status: list[PartyStatsGroupItem]
    annual_full_count: int
    annual_conversions: int


class PoliticalStatusStats(BaseModel):
    total: int
    by_status: list[PartyStatsGroupItem]
    by_class: list[PartyStatsGroupItem]
    by_grade: list[PartyStatsGroupItem]


class PartyStatsResponse(BaseModel):
    member_counts: PartyMemberCountsStats
    participation: PartyParticipationStats
    materials: PartyMaterialsStats
    development: PartyDevelopmentStats
    political_counts: PoliticalStatusStats
    league_participation: PartyParticipationStats
    political_materials: dict[str, Any]
    filters: dict[str, Any]


class PartyExportRequest(BaseModel):
    format: Literal["csv"] = "csv"
    export_type: Literal["stats", "members", "participants"] = "stats"
    class_name: str | None = None
    grade: str | None = None
    year: int | None = Field(default=None, ge=1900, le=9999)
    category: PartyActivityCategory | None = None
    party_type: str | None = None
    apply_status: str | None = None
    activity_id: int | None = Field(default=None, gt=0)
    max_rows: int = Field(default=5000, ge=1, le=5000)

    model_config = {"extra": "forbid"}


class PartyMineResponse(BaseModel):
    party: dict[str, Any]
    records: list[PartyParticipationRecord]
    participation_records: list[PartyParticipationRecord]


class PartyAchievementLinkRequest(BaseModel):
    link_type: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "link_type", "type", "source_kind", "source_type"
        ),
    )
    activity_id: int | None = Field(default=None, gt=0)
    user_id: int | None = Field(default=None, gt=0)
    achievement_category: Literal["organization", "social"] | None = None

    model_config = {"extra": "forbid", "populate_by_name": True}


PartyActivityInfo.model_rebuild()


class PoliticalStatusApply(BaseModel):
    to_status: Literal["共青团员", "群众"]
    remark: str | None = Field(default=None, max_length=1000)

    model_config = {"extra": "forbid"}


class PoliticalStatusReviewAction(BaseModel):
    remark: str | None = Field(default=None, max_length=1000)

    model_config = {"extra": "forbid"}


class PoliticalStatusReviewInfo(BaseModel):
    id: int
    user_id: int
    student_no: str = ""
    user_name: str = ""
    from_status: str
    to_status: str
    status: Literal["pending", "approved", "rejected"]
    submitted_by: int
    submitted_at: datetime
    reviewed_by: int | None
    reviewed_at: datetime | None
    remark: str | None

    model_config = {"from_attributes": True}


class PoliticalStatusMineResponse(BaseModel):
    political_status: str
    political_status_updated_at: datetime | None
    latest_review: PoliticalStatusReviewInfo | None


class PoliticalStatusRosterInfo(BaseModel):
    user_id: int
    student_no: str
    name: str
    political_status: str
    political_status_updated_at: datetime | None = None
    class_name: str | None = None
    grade: str | None = None
    party_type: str | None = None
    apply_status: str | None = None
    latest_review: PoliticalStatusReviewInfo | None = None


class PoliticalStatusRosterListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[PoliticalStatusRosterInfo]


class PoliticalStatusReviewListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[PoliticalStatusReviewInfo]


PoliticalMaterialStatus = Literal["draft", "published", "offline"]


class PoliticalLearningMaterialCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    applicable_roles: list[str] = Field(default_factory=list)
    target_user_ids: list[int] = Field(default_factory=list)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    status: PoliticalMaterialStatus = "draft"

    model_config = {"extra": "forbid", "populate_by_name": True}


class PoliticalLearningMaterialUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    applicable_roles: list[str] | None = None
    target_user_ids: list[int] | None = None
    attachments: list[dict[str, Any]] | None = None
    status: PoliticalMaterialStatus | None = None

    model_config = {"extra": "forbid", "populate_by_name": True}


class PoliticalLearningMaterialInfo(BaseModel):
    id: int
    title: str
    description: str | None
    applicable_roles: list[str]
    target_user_ids: list[int]
    attachments: list[dict[str, Any]]
    status: PoliticalMaterialStatus
    created_by: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class PoliticalLearningMaterialListResponse(BaseModel):
    total: int
    items: list[PoliticalLearningMaterialInfo]
