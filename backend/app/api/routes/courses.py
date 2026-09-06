import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.errors import AppException
from backend.app.repositories.school_repo import CourseRepository, ScheduleRepository
from backend.app.schemas.school import (
    CourseCreate,
    CourseUpdate,
    CourseInfo,
    CourseListResponse,
    ScheduleCreate,
    ScheduleInfo,
    CourseWithSchedules,
)
from backend.app.api.deps import get_current_user, require_admin
from backend.app.services.course_nl_service import CourseNLService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/courses", response_model=CourseInfo)
async def create_course(
    form: CourseCreate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    course = CourseRepository.create(
        db, created_by=current_user.id,
        name=form.name, teacher=form.teacher, description=form.description,
        color=form.color, semester=form.semester,
    )
    return CourseInfo.model_validate(course)


@router.get("/courses", response_model=CourseListResponse)
async def list_courses(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    q: str = Query(None),
    semester: str = Query(None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items, total = CourseRepository.list(db, page=page, page_size=page_size, q=q, semester=semester)
    return CourseListResponse(total=total, items=[CourseInfo.model_validate(c) for c in items])


@router.get("/courses/{course_id}", response_model=CourseInfo)
async def get_course(
    course_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    course = CourseRepository.get_by_id(db, course_id)
    if not course:
        raise AppException("COURSE_NOT_FOUND", "课程不存在", 404)
    return CourseInfo.model_validate(course)


@router.put("/courses/{course_id}", response_model=CourseInfo)
async def update_course(
    course_id: int,
    form: CourseUpdate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    course = CourseRepository.get_by_id(db, course_id)
    if not course:
        raise AppException("COURSE_NOT_FOUND", "课程不存在", 404)
    course = CourseRepository.update(
        db, course,
        name=form.name, teacher=form.teacher, description=form.description,
        color=form.color, semester=form.semester,
    )
    return CourseInfo.model_validate(course)


@router.delete("/courses/{course_id}")
async def delete_course(
    course_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    course = CourseRepository.get_by_id(db, course_id)
    if not course:
        raise AppException("COURSE_NOT_FOUND", "课程不存在", 404)
    CourseRepository.soft_delete(db, course)
    return {"message": "课程已删除"}


@router.get("/courses/{course_id}/schedules", response_model=list[ScheduleInfo])
async def list_schedules(
    course_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    course = CourseRepository.get_by_id(db, course_id)
    if not course:
        raise AppException("COURSE_NOT_FOUND", "课程不存在", 404)
    items = ScheduleRepository.list_by_course(db, course_id)
    return [ScheduleInfo.model_validate(s) for s in items]


@router.put("/courses/{course_id}/schedules", response_model=list[ScheduleInfo])
async def replace_schedules(
    course_id: int,
    schedules: list[ScheduleCreate],
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """覆盖式设置课程时间安排"""
    course = CourseRepository.get_by_id(db, course_id)
    if not course:
        raise AppException("COURSE_NOT_FOUND", "课程不存在", 404)
    # 校验 start <= end
    for s in schedules:
        if s.start_period > s.end_period:
            raise AppException("INVALID_SCHEDULE", "开始节次不能大于结束节次", 400)
    data = [s.model_dump() for s in schedules]
    items = ScheduleRepository.replace_for_course(db, course_id, data)
    return [ScheduleInfo.model_validate(s) for s in items]


@router.get("/schedule/today", response_model=list[CourseWithSchedules])
async def today_schedule(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """今日课表"""
    from datetime import datetime
    weekday = datetime.now().isoweekday()
    courses, _ = CourseRepository.list(db, page=1, page_size=500)
    result = []
    for c in courses:
        schedules = ScheduleRepository.list_by_weekday(db, weekday, [c.id])
        if schedules:
            result.append(CourseWithSchedules(
                course=CourseInfo.model_validate(c),
                schedules=[ScheduleInfo.model_validate(s) for s in schedules],
            ))
    return result


@router.get("/schedule/week", response_model=list[CourseWithSchedules])
async def week_schedule(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """本周课表（按课程聚合）"""
    courses, _ = CourseRepository.list(db, page=1, page_size=500)
    result = []
    for c in courses:
        schedules = ScheduleRepository.list_by_course(db, c.id)
        if schedules:
            result.append(CourseWithSchedules(
                course=CourseInfo.model_validate(c),
                schedules=[ScheduleInfo.model_validate(s) for s in schedules],
            ))
    return result


@router.post("/courses/query-nl")
async def query_course_nl(
    body: dict,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """自然语言课程查询，如「今天有什么课」「数据结构什么时候」"""
    text = (body or {}).get("text", "").strip()
    if not text:
        raise AppException("INVALID_INPUT", "查询内容为空", 400)
    return CourseNLService.query(db, text)
