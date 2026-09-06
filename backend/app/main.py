import logging
import uuid
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.core.config import settings, validate_settings
from backend.app.core.database import engine, Base
from backend.app.core.errors import register_exception_handlers
from backend.app.core.logging import setup_logging

_log = logging.getLogger("app")


def create_app() -> FastAPI:
    setup_logging()
    _log.info("Step 1/7 | 日志系统初始化完成")

    validate_settings()
    _log.info("Step 2/7 | 配置校验通过")

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    _log.info("Step 3/7 | FastAPI 应用创建完成 (title=%s, version=%s)", settings.APP_NAME, settings.APP_VERSION)

    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    _log.info("Step 4/7 | CORS 中间件注册 (origins=%d, allow_credentials=True)", len(origins))

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start_time = time.time()
        response = await call_next(request)
        duration_ms = round((time.time() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms}ms"
        return response

    register_exception_handlers(app)
    _log.info("Step 5/7 | 异常处理器注册完成")

    # 导入所有模型确保 create_all 能建全部表
    from backend.app.models.user import User, AlumniConversionRequest
    from backend.app.models.user_session import UserSession
    from backend.app.models.chat import ChatSession, ChatMessage, ChatMessageAttachment, ChatMessageCitation
    from backend.app.models.chat_request import ChatRequest
    from backend.app.models.token_quota import (
        TokenQuotaPolicy, UserTokenQuotaOverride, UserDailyTokenUsage,
        ChatTokenUsageEvent, TokenQuotaAuditLog,
    )
    from backend.app.models.file import KnowledgeFile, FileChunk, KnowledgeFolder, KnowledgeFileVersion
    from backend.app.models.school import (
        Course, CourseSchedule, Assignment, Submission, SubmissionVersion, AssignmentAttachment, SubmissionAttachment,
    )
    from backend.app.models.notification import Notification
    from backend.app.models.skill import Skill, SkillCall
    from backend.app.models.skill_embedding import SkillEmbedding
    from backend.app.models.audit import AuditLog
    from backend.app.models.runtime_config import RuntimeConfig
    from backend.app.models.announcement import (
        AnnouncementSource, SchoolAnnouncement, AnnouncementOrigin, AnnouncementAttachment,
        AnnouncementTaskRun, AnnouncementDigest, AnnouncementDigestDelivery,
    )
    from backend.app.models.achievement import Achievement
    from backend.app.models.resource import Resource, ResourceFavorite, ResourceLike
    from backend.app.models.teacher import TeacherDirection, CommunicationApplication, LearningPlan
    from backend.app.models.mentor_selection import (
        MentorSelectionBatch, MentorSelectionBatchStudent, MentorSelectionBatchMentor,
        MentorPreferenceSubmission, MentorPreferenceItem, MentorDecisionSubmission,
        MentorDecisionItem, MentorMatchResultVersion, MentorMatchResultItem,
        MentorSelectionTaskRun, MentorSelectionNotificationDelivery,
    )
    from backend.app.models.party import (
        PartyActivity,
        PartyActivityParticipant,
        PartyMaterial,
        PoliticalStatusReview,
        PoliticalLearningMaterial,
    )
    # Persistent databases are schema-managed by Alembic.  Keeping create_all
    # for ephemeral test databases avoids silently altering the protected dev DB.
    if settings.DB_URL.endswith(":memory:"):
        Base.metadata.create_all(bind=engine)
        _log.info("Step 6/7 | 内存测试数据库表初始化完成 (models=%d)", len(Base.metadata.tables))
    else:
        _log.info("Step 6/7 | 持久数据库由 Alembic 管理，跳过 create_all")

    # 审计日志中间件
    from backend.app.core.audit_middleware import AuditMiddleware
    app.add_middleware(AuditMiddleware)
    _log.info("       | 中间件: AuditMiddleware ✓")

    # 幂等键中间件（写操作防重复提交）
    from backend.app.core.idempotency import IdempotencyMiddleware
    app.add_middleware(IdempotencyMiddleware)
    _log.info("       | 中间件: IdempotencyMiddleware ✓")

    # 通用 API 限流中间件
    from backend.app.core.rate_limit import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware)
    _log.info("       | 中间件: RateLimitMiddleware ✓")

    # 文件清理后台任务（非 test 环境启动）
    @app.on_event("startup")
    async def _start_cleanup():
        _log.info("Step 7/7 | 启动事件: 启动文件清理后台任务")
        from backend.app.workers.file_cleanup import start_cleanup_loop
        start_cleanup_loop(app)

    @app.on_event("startup")
    async def _load_runtime_config():
        from backend.app.core.database import SessionLocal
        from backend.app.services.runtime_config_service import RuntimeConfigService
        db = SessionLocal()
        try:
            RuntimeConfigService.load(db)
        except Exception as exc:
            # A legacy database can still boot before the platform migration is applied.
            _log.warning("运行时配置表不可用，继续使用环境变量配置：%s", exc)
        finally:
            db.close()

    # 种子内置 Skill
    try:
        from backend.app.core.database import SessionLocal
        from backend.app.repositories.skill_repo import SkillRepository
        _seed_db = SessionLocal()
        try:
            added = SkillRepository.seed_system_skills(_seed_db)
            if added:
                _log.info("种子数据: 写入 %d 个系统 Skill", added)
        finally:
            _seed_db.close()
    except Exception as e:
        _log.warning("种子数据: Skill 种子写入失败 (%s)", e)

    try:
        from backend.app.repositories.announcement_repo import AnnouncementSourceRepository
        _seed_db = SessionLocal()
        try:
            AnnouncementSourceRepository.seed_defaults(_seed_db)
        finally:
            _seed_db.close()
    except Exception as e:
        _log.warning("announcement source seed failed (%s)", e)

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}

    from backend.app.api.routes.auth import router as auth_router
    from backend.app.api.routes.users import router as users_router
    from backend.app.api.routes.admin_users import router as admin_users_router
    from backend.app.api.routes.chat import router as chat_router
    from backend.app.api.routes.knowledge import router as knowledge_router
    from backend.app.api.routes.class_knowledge import router as class_knowledge_router
    from backend.app.api.routes.courses import router as courses_router
    from backend.app.api.routes.assignments import router as assignments_router
    from backend.app.api.routes.notifications import router as notifications_router
    from backend.app.api.routes.admin_skills import router as admin_skills_router
    from backend.app.api.routes.mcp import router as mcp_router
    from backend.app.api.routes.admin_audit import router as admin_audit_router
    from backend.app.api.routes.admin_stats import router as admin_stats_router
    from backend.app.api.routes.admin_config import router as admin_config_router
    from backend.app.api.routes.chat_usage import router as chat_usage_router

    # V2.0 新增路由
    from backend.app.api.routes.achievement_stats import router as achievement_stats_router
    from backend.app.api.routes.achievements import router as achievements_router
    from backend.app.api.routes.resources import router as resources_router
    from backend.app.api.routes.teachers import router as teachers_router
    from backend.app.api.routes.applications import router as applications_router
    from backend.app.api.routes.recommendations import router as recommendations_router
    from backend.app.api.routes.confirm import router as confirm_router
    from backend.app.api.routes.party import router as party_router
    from backend.app.api.routes.business_skills import router as business_skills_router
    from backend.app.api.routes.skills import router as skills_router
    from backend.app.api.routes.school_announcements import router as school_announcements_router
    from backend.app.api.routes.admin_announcements import router as admin_announcements_router
    from backend.app.api.routes.mentor_selection import router as mentor_selection_router

    app.include_router(auth_router, prefix="/api/v1/auth", tags=["认证"])
    app.include_router(users_router, prefix="/api/v1/users", tags=["用户"])
    app.include_router(admin_users_router, prefix="/api/v1/admin", tags=["管理-用户"])
    app.include_router(chat_router, prefix="/api/v1/chat", tags=["对话"])
    app.include_router(knowledge_router, prefix="/api/v1/knowledge", tags=["知识库-个人"])
    app.include_router(class_knowledge_router, prefix="/api/v1/class-knowledge", tags=["知识库-班级"])
    app.include_router(courses_router, prefix="/api/v1", tags=["课程"])
    app.include_router(assignments_router, prefix="/api/v1", tags=["作业"])
    app.include_router(notifications_router, prefix="/api/v1", tags=["通知"])
    app.include_router(admin_skills_router, prefix="/api/v1/admin", tags=["管理-Skill"])
    app.include_router(mcp_router, prefix="/api/v1/mcp", tags=["MCP工具"])
    app.include_router(admin_audit_router, prefix="/api/v1/admin", tags=["管理-审计"])
    app.include_router(admin_stats_router, prefix="/api/v1/admin", tags=["管理-统计"])
    app.include_router(admin_config_router, prefix="/api/v1/admin", tags=["管理-配置"])
    app.include_router(chat_usage_router, prefix="/api/v1", tags=["对话-额度与用量"])

    # V2.0 路由挂载
    app.include_router(achievement_stats_router, prefix="/api/v1/achievements", tags=["成果统计"])
    app.include_router(achievements_router, prefix="/api/v1/achievements", tags=["成果管理"])
    app.include_router(resources_router, prefix="/api/v1/resources", tags=["资源社区"])
    app.include_router(teachers_router, prefix="/api/v1/teachers", tags=["教师"])
    app.include_router(applications_router, prefix="/api/v1/applications", tags=["交流申请"])
    app.include_router(recommendations_router, prefix="/api/v1/recommendations", tags=["个性化推荐"])
    app.include_router(confirm_router, prefix="/api/v1/confirm", tags=["任务确认"])
    app.include_router(party_router, prefix="/api/v1/party", tags=["党建-党员档案"])
    app.include_router(
        business_skills_router,
        prefix="/api/v1/skills/business",
        tags=["业务-Skill"],
    )
    app.include_router(skills_router, prefix="/api/v1/skills", tags=["Skill"])
    app.include_router(school_announcements_router, prefix="/api/v1", tags=["学校公告"])
    app.include_router(admin_announcements_router, prefix="/api/v1/admin", tags=["公告运维"])
    app.include_router(
        mentor_selection_router,
        prefix="/api/v1/mentor-selection",
        tags=["学术导师双选"],
    )

    # --- 静态文件服务（前端） ---
    import os
    _frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
    if os.path.isdir(_frontend_dir):
        app.mount("/static", StaticFiles(directory=_frontend_dir), name="frontend")
        _log.info("前端静态文件挂载: %s -> /static", _frontend_dir)
    else:
        _log.warning("前端目录不存在: %s", _frontend_dir)

    @app.get("/")
    async def root():
        # 如果有前端 index.html，返回它；否则返回 API 信息
        _index = os.path.join(_frontend_dir, "index.html")
        if os.path.isfile(_index):
            from fastapi.responses import FileResponse
            return FileResponse(_index)
        return {"name": settings.APP_NAME, "version": settings.APP_VERSION, "docs": "/docs"}

    _log.info("═══════════════════════════════════════════════════════")
    _log.info("应用初始化完成！")
    _log.info("  版本:      %s", settings.APP_VERSION)
    _log.info("  环境:      %s", settings.ENV)
    _log.info("  路由数:    %d", len(app.routes))
    _log.info("  文档:      http://0.0.0.0:8000/docs")
    _log.info("  ReDoc:     http://0.0.0.0:8000/redoc")
    _log.info("  健康检查:  http://0.0.0.0:8000/health")
    _log.info("  AI 模式:   %s", "真实 AI (DeepSeek)" if settings.AI_API_KEY else "Mock 模拟")
    _log.info("═══════════════════════════════════════════════════════")

    return app


app = create_app()
