"""Agent 工具 - 数据库查询和管理工具

这些工具提供给 Agent 使用，用于查询和管理平台数据。
查询工具对所有用户开放，管理工具仅对管理员开放。
"""

import json
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.app.repositories.user_repo import UserRepository
from backend.app.repositories.achievement_repo import AchievementRepository
from backend.app.repositories.resource_repo import ResourceRepository
from backend.app.repositories.teacher_repo import TeacherRepository
from backend.app.repositories.chat_repo import ChatRepository
from backend.app.repositories.skill_repo import SkillRepository
from backend.app.repositories.notification_repo import NotificationRepository
from backend.app.models.user import User, UserRole, UserStatus

logger = logging.getLogger(__name__)


class AgentTools:
    """Agent 可用的数据库工具集合"""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self._user: User | None = None
        self.business_skill_names: list[str] = []

    @property
    def user(self):
        if self._user is None:
            self._user = UserRepository.get_by_id(self.db, self.user_id)
        return self._user

    @property
    def user_role(self) -> str:
        return self.user.role if self.user else "unknown"

    @property
    def is_admin(self) -> bool:
        return self.user_role == UserRole.ADMIN.value

    @property
    def is_teacher(self) -> bool:
        return self.user_role == UserRole.TEACHER.value

    # ========== 业务 Skill 工具（复用统一执行层） ==========

    async def _execute_business_skill(self, skill_name: str, user_input: str) -> str:
        from backend.app.ai.business_skills.service import BusinessSkillService

        self.business_skill_names.append(skill_name)
        result = await BusinessSkillService.execute(skill_name, user_input, self.user, self.db)
        return json.dumps(result, ensure_ascii=False, default=str)

    async def recommend_competitions(self, user_input: str) -> str:
        """根据当前用户画像和补充条件推荐竞赛。"""
        return await self._execute_business_skill("competition_recommend", user_input)

    async def match_mentors(self, user_input: str) -> str:
        """根据项目描述匹配导师和研究方向。"""
        return await self._execute_business_skill("mentor_match", user_input)

    async def query_party(self, user_input: str) -> str:
        """按当前用户权限执行只读党建查询。"""
        return await self._execute_business_skill("party_query", user_input)

    def list_party_members(self, **kwargs) -> str:
        from backend.app.services.party_skill_boundary import PartySkillBoundary

        return json.dumps(PartySkillBoundary(self.db, self.user).list_party_members(**kwargs), ensure_ascii=False, default=str)

    def get_party_member(self, user_id: int) -> str:
        from backend.app.services.party_skill_boundary import PartySkillBoundary

        return json.dumps(PartySkillBoundary(self.db, self.user).get_party_member(user_id), ensure_ascii=False, default=str)

    def list_party_activities(self, **kwargs) -> str:
        from backend.app.services.party_skill_boundary import PartySkillBoundary

        return json.dumps(
            PartySkillBoundary(self.db, self.user).list_party_activities(**kwargs), ensure_ascii=False, default=str
        )

    def get_party_activity(self, activity_id: int) -> str:
        from backend.app.services.party_skill_boundary import PartySkillBoundary

        return json.dumps(
            PartySkillBoundary(self.db, self.user).get_party_activity(activity_id), ensure_ascii=False, default=str
        )

    def get_party_my_records(self) -> str:
        from backend.app.services.party_skill_boundary import PartySkillBoundary

        return json.dumps(PartySkillBoundary(self.db, self.user).get_party_my_records(), ensure_ascii=False, default=str)

    def get_my_political_status(self) -> str:
        from backend.app.services.party_skill_boundary import PartySkillBoundary

        return json.dumps(
            PartySkillBoundary(self.db, self.user).get_my_political_status(),
            ensure_ascii=False,
            default=str,
        )

    def list_political_learning_materials(self) -> str:
        from backend.app.services.party_skill_boundary import PartySkillBoundary

        return json.dumps(
            PartySkillBoundary(self.db, self.user).list_political_learning_materials(),
            ensure_ascii=False,
            default=str,
        )

    def get_political_status_stats(self, **kwargs) -> str:
        from backend.app.services.party_skill_boundary import PartySkillBoundary

        return json.dumps(
            PartySkillBoundary(self.db, self.user).get_political_status_stats(
                **kwargs
            ),
            ensure_ascii=False,
            default=str,
        )

    async def manage_achievements(self, user_input: str) -> str:
        """查询本人成果，或为成果写操作生成待确认预览。"""
        return await self._execute_business_skill("achievement_manage", user_input)

    def list_my_achievements(
        self,
        category: str | None = None,
        status: str | None = None,
        year: str | None = None,
    ) -> str:
        items, total = AchievementRepository.list_by_user(
            self.db, self.user_id, 1, 100, category, status, year
        )
        return json.dumps(
            {
                "total": total,
                "items": [
                    {
                        "id": item.id,
                        "title": item.title,
                        "category": item.category,
                        "status": item.status,
                        "achievement_date": item.achievement_date,
                        "details": item.details,
                    }
                    for item in items
                ],
            },
            ensure_ascii=False,
            default=str,
        )

    def get_my_achievement(self, achievement_id: int) -> str:
        item = AchievementRepository.get_by_id_for_user(self.db, achievement_id, self.user_id)
        if item is None:
            return json.dumps({"error": "成果不存在"}, ensure_ascii=False)
        return json.dumps(
            {
                "id": item.id,
                "title": item.title,
                "category": item.category,
                "status": item.status,
                "details": item.details,
                "proofs": item.proofs,
            },
            ensure_ascii=False,
            default=str,
        )

    def get_achievement_templates(self) -> str:
        from backend.app.services.achievement_templates import serialize_templates

        return json.dumps(serialize_templates(), ensure_ascii=False)

    async def create_achievement(self, data: dict, confirmation_token: str | None = None) -> str:
        payload = dict(data)
        if confirmation_token:
            payload["confirmation_token"] = confirmation_token
        return await self.manage_achievements("新增成果 " + json.dumps(payload, ensure_ascii=False))

    async def update_achievement(
        self,
        achievement_id: int,
        changes: dict,
        confirmation_token: str | None = None,
    ) -> str:
        payload = {"achievement_id": achievement_id, **changes}
        if confirmation_token:
            payload["confirmation_token"] = confirmation_token
        return await self.manage_achievements("修改成果 " + json.dumps(payload, ensure_ascii=False))

    async def delete_achievement(
        self,
        achievement_id: int,
        confirmation_token: str | None = None,
    ) -> str:
        payload: dict[str, Any] = {"achievement_id": achievement_id}
        if confirmation_token:
            payload["confirmation_token"] = confirmation_token
        return await self.manage_achievements("删除成果 " + json.dumps(payload, ensure_ascii=False))

    # ========== 查询工具（所有用户可用） ==========

    def get_user_info(self, target_user_id: Optional[int] = None, student_no: Optional[str] = None) -> str:
        """
        查询用户信息。
        - 管理员可查询任意用户
        - 教师可查询自己的信息和学生信息
        - 其他角色只能查询自己的信息
        """
        try:
            if student_no:
                target = UserRepository.get_by_student_no(self.db, student_no)
            elif target_user_id:
                target = UserRepository.get_by_id(self.db, target_user_id)
            else:
                target = self.user

            if not target:
                return json.dumps({"error": "用户不存在"}, ensure_ascii=False)

            # 权限检查
            if not self.is_admin and target.id != self.user_id:
                if not self.is_teacher:
                    return json.dumps({"error": "无权查询其他用户信息"}, ensure_ascii=False)

            info = {
                "id": target.id,
                "name": target.name,
                "student_no": target.student_no,
                "role": target.role,
                "status": target.status,
                "profile": target.profile,
                "created_at": target.created_at.isoformat() if target.created_at else None,
            }
            return json.dumps(info, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("get_user_info error: %s", e)
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def list_users(self, role: Optional[str] = None, status: Optional[str] = None,
                   page: int = 1, page_size: int = 20) -> str:
        """
        查询用户列表。仅管理员可用。
        """
        if not self.is_admin:
            return json.dumps({"error": "仅管理员可查询用户列表"}, ensure_ascii=False)

        try:
            users, total = UserRepository.list(self.db, page=page, page_size=page_size,
                                               role=role, status=status)
            items = [{
                "id": u.id,
                "name": u.name,
                "student_no": u.student_no,
                "role": u.role,
                "status": u.status,
            } for u in users]
            return json.dumps({"total": total, "page": page, "page_size": page_size, "items": items},
                              ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("list_users error: %s", e)
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def count_users(self) -> str:
        """统计系统用户数量。"""
        if not self.is_admin:
            return json.dumps({"error": "仅管理员可查询统计数据"}, ensure_ascii=False)

        try:
            stats = {
                "total": UserRepository.count(self.db),
                "admins": UserRepository.count(self.db, role=UserRole.ADMIN.value),
                "teachers": UserRepository.count(self.db, role=UserRole.TEACHER.value),
                "students": UserRepository.count(self.db, role=UserRole.STUDENT.value),
                "alumni": UserRepository.count(self.db, role=UserRole.ALUMNI.value),
                "active": UserRepository.count(self.db, status=UserStatus.ACTIVE.value),
                "pending_change": UserRepository.count(self.db, status=UserStatus.PENDING_CHANGE.value),
                "disabled": UserRepository.count(self.db, status=UserStatus.DISABLED.value),
            }
            return json.dumps(stats, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("count_users error: %s", e)
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def list_achievements(self, user_id: Optional[int] = None, status: Optional[str] = None,
                          category: Optional[str] = None, q: Optional[str] = None,
                          page: int = 1, page_size: int = 20) -> str:
        """
        查询成果列表。
        - 管理员可查询所有成果
        - 教师可查询所有已审核成果
        - 其他角色只能查询公开的成果或自己的成果
        """
        try:
            if self.is_admin:
                achievements, total = AchievementRepository.list_all(
                    self.db, page=page, page_size=page_size, status=status, q=q
                )
            elif self.is_teacher:
                achievements, total = AchievementRepository.list_all(
                    self.db, page=page, page_size=page_size, status=status, q=q
                )
            elif user_id and user_id == self.user_id:
                achievements, total = AchievementRepository.list_by_user(
                    self.db, user_id=user_id, page=page, page_size=page_size,
                    category=category, status=status
                )
            else:
                achievements, total = AchievementRepository.list_public(
                    self.db, page=page, page_size=page_size, category=category, q=q
                )

            items = [{
                "id": a.id,
                "title": a.title,
                "description": a.description,
                "category": a.category,
                "user_id": a.user_id,
                "status": a.status,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            } for a in achievements]
            return json.dumps({"total": total, "items": items}, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("list_achievements error: %s", e)
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def list_resources(self, type: Optional[str] = None, q: Optional[str] = None,
                       tag: Optional[str] = None, page: int = 1, page_size: int = 20) -> str:
        """查询资源列表。"""
        try:
            resources, total = ResourceRepository.list_approved(
                self.db, page=page, page_size=page_size, type=type, q=q, tag=tag
            )
            items = [{
                "id": r.id,
                "title": r.title,
                "content": (r.content or "")[:200] + "..." if len(r.content or "") > 200 else (r.content or ""),
                "type": r.type,
                "author_id": r.author_id,
                "likes": r.like_count,
                "views": r.view_count,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            } for r in resources]
            return json.dumps({"total": total, "items": items}, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("list_resources error: %s", e)
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def list_teachers(self, q: Optional[str] = None, tag: Optional[str] = None,
                      page: int = 1, page_size: int = 20) -> str:
        """查询教师列表。"""
        try:
            teachers, total = TeacherRepository.match_teachers(
                self.db, q=q, tag=tag, page=page, page_size=page_size
            )
            items = [{
                "id": t.id,
                "name": t.name,
                "student_no": t.student_no,
                "role": t.role,
            } for t in teachers]
            return json.dumps({"total": total, "items": items}, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("list_teachers error: %s", e)
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def list_teacher_directions(self, teacher_id: Optional[int] = None, active_only: bool = False) -> str:
        """查询教师研究方向。"""
        try:
            tid = teacher_id or self.user_id
            directions = TeacherRepository.list_by_teacher(self.db, tid, active_only=active_only)
            items = [{
                "id": d.id,
                "title": d.title,
                "description": d.description,
                "tags": d.tags,
                "is_active": d.is_active,
            } for d in directions]
            return json.dumps({"items": items}, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("list_teacher_directions error: %s", e)
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def list_applications(self, status: Optional[str] = None, page: int = 1, page_size: int = 20) -> str:
        """
        查询交流申请。
        - 管理员可查询所有
        - 教师可查询自己的
        - 学生可查询自己的
        """
        try:
            if self.is_admin:
                applications, total = TeacherRepository.list_applications_by_teacher(
                    self.db, teacher_id=0, page=page, page_size=page_size, status=status
                )
                # 管理员获取全部
                from backend.app.models.teacher import CommunicationApplication
                query = self.db.query(CommunicationApplication).filter(
                    CommunicationApplication.deleted_at.is_(None)
                )
                if status:
                    query = query.filter(CommunicationApplication.status == status)
                total = query.count()
                applications = query.order_by(CommunicationApplication.created_at.desc()) \
                    .offset((page - 1) * page_size).limit(page_size).all()
            elif self.is_teacher:
                applications, total = TeacherRepository.list_applications_by_teacher(
                    self.db, teacher_id=self.user_id, page=page, page_size=page_size, status=status
                )
            else:
                applications, total = TeacherRepository.list_applications_by_student(
                    self.db, student_id=self.user_id, page=page, page_size=page_size, status=status
                )

            items = [{
                "id": a.id,
                "student_id": a.student_id,
                "teacher_id": a.teacher_id,
                "message": a.message,
                "status": a.status,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            } for a in applications]
            return json.dumps({"total": total, "items": items}, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("list_applications error: %s", e)
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def list_learning_plans(self, user_id: Optional[int] = None,
                            is_completed: Optional[bool] = None,
                            page: int = 1, page_size: int = 20) -> str:
        """查询学习计划。"""
        try:
            uid = user_id or self.user_id
            if not self.is_admin and uid != self.user_id:
                return json.dumps({"error": "无权查询其他用户的学习计划"}, ensure_ascii=False)

            plans, total = TeacherRepository.list_plans(
                self.db, user_id=uid, page=page, page_size=page_size,
                is_completed=is_completed
            )
            items = [{
                "id": p.id,
                "title": p.title,
                "content": p.description,
                "is_completed": p.is_completed,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            } for p in plans]
            return json.dumps({"total": total, "items": items}, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("list_learning_plans error: %s", e)
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def list_notifications(self, page: int = 1, page_size: int = 20) -> str:
        """查询当前用户的通知。"""
        try:
            from backend.app.models.notification import Notification
            query = self.db.query(Notification).filter(
                Notification.user_id == self.user_id
            )
            total = query.count()
            notifications = query.order_by(Notification.created_at.desc()) \
                .offset((page - 1) * page_size).limit(page_size).all()
            items = [{
                "id": n.id,
                "title": n.title,
                "content": n.content,
                "type": n.type,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            } for n in notifications]
            return json.dumps({"total": total, "items": items}, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("list_notifications error: %s", e)
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def list_chat_sessions(self, page: int = 1, page_size: int = 20) -> str:
        """查询当前用户的聊天会话。"""
        try:
            sessions, total = ChatRepository.list_sessions(
                self.db, user_id=self.user_id, page=page, page_size=page_size
            )
            items = [{
                "id": s.id,
                "title": s.title,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            } for s in sessions]
            return json.dumps({"total": total, "items": items}, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("list_chat_sessions error: %s", e)
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def get_platform_stats(self) -> str:
        """获取平台总体统计数据。仅管理员可用。"""
        if not self.is_admin:
            return json.dumps({"error": "仅管理员可查询平台统计"}, ensure_ascii=False)

        try:
            stats = {
                "users": {
                    "total": UserRepository.count(self.db),
                    "by_role": {
                        "admin": UserRepository.count(self.db, role="admin"),
                        "teacher": UserRepository.count(self.db, role="teacher"),
                        "student": UserRepository.count(self.db, role="student"),
                        "alumni": UserRepository.count(self.db, role="alumni"),
                    },
                },
                "achievements": AchievementRepository.list_all(self.db, page=1, page_size=1)[1],
                "resources": ResourceRepository.list_approved(self.db, page=1, page_size=1)[1],
                "skills": len(SkillRepository.list(self.db)),
            }
            return json.dumps(stats, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("get_platform_stats error: %s", e)
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    # ========== 管理工具（仅管理员可用，需二次确认） ==========

    def admin_create_user(self, student_no: str, name: str, role: str = "student",
                          initial_password: str = "123456") -> str:
        """
        创建新用户。仅管理员可用。
        """
        if not self.is_admin:
            return json.dumps({"error": "仅管理员可创建用户"}, ensure_ascii=False)

        try:
            existing = UserRepository.get_by_student_no(self.db, student_no)
            if existing:
                return json.dumps({"error": f"学号 {student_no} 已存在"}, ensure_ascii=False)

            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            password_hash = pwd_context.hash(initial_password)

            user = UserRepository.create(
                self.db, student_no=student_no, name=name,
                password_hash=password_hash, role=role,
                status=UserStatus.PENDING_CHANGE.value
            )
            return json.dumps({
                "success": True,
                "message": "用户创建成功",
                "user": {"id": user.id, "student_no": user.student_no, "name": user.name, "role": user.role},
                "temporary_password": initial_password,
            }, ensure_ascii=False, indent=2)
        except ImportError:
            return json.dumps({"error": "密码哈希模块不可用"}, ensure_ascii=False)
        except Exception as e:
            logger.error("admin_create_user error: %s", e)
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def admin_reset_password(self, user_id: int, new_password: str = "123456") -> str:
        """
        重置用户密码。仅管理员可用。
        """
        if not self.is_admin:
            return json.dumps({"error": "仅管理员可重置密码"}, ensure_ascii=False)

        try:
            user = UserRepository.get_by_id(self.db, user_id)
            if not user:
                return json.dumps({"error": "用户不存在"}, ensure_ascii=False)

            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            password_hash = pwd_context.hash(new_password)

            UserRepository.update(
                self.db, user,
                password_hash=password_hash,
                status=UserStatus.PENDING_CHANGE.value
            )
            return json.dumps({
                "success": True,
                "message": f"密码已重置为: {new_password}，用户需首次登录修改",
                "user_id": user_id,
            }, ensure_ascii=False, indent=2)
        except ImportError:
            return json.dumps({"error": "密码哈希模块不可用"}, ensure_ascii=False)
        except Exception as e:
            logger.error("admin_reset_password error: %s", e)
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def admin_update_user_status(self, user_id: int, status: str) -> str:
        """
        更新用户状态（active/disabled/pending_change）。仅管理员可用。
        """
        if not self.is_admin:
            return json.dumps({"error": "仅管理员可更新用户状态"}, ensure_ascii=False)

        valid_statuses = [UserStatus.ACTIVE.value, UserStatus.DISABLED.value, UserStatus.PENDING_CHANGE.value]
        if status not in valid_statuses:
            return json.dumps({"error": f"无效状态值: {status}，有效值: {valid_statuses}"},
                              ensure_ascii=False)

        try:
            user = UserRepository.get_by_id(self.db, user_id)
            if not user:
                return json.dumps({"error": "用户不存在"}, ensure_ascii=False)

            UserRepository.update(self.db, user, status=status)
            return json.dumps({
                "success": True,
                "message": f"用户 {user.name} 状态已更新为: {status}",
                "user_id": user_id,
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("admin_update_user_status error: %s", e)
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def admin_delete_user(self, user_id: int) -> str:
        """
        软删除用户（标记为已删除）。仅管理员可用。
        """
        if not self.is_admin:
            return json.dumps({"error": "仅管理员可删除用户"}, ensure_ascii=False)

        try:
            user = UserRepository.get_by_id(self.db, user_id)
            if not user:
                return json.dumps({"error": "用户不存在"}, ensure_ascii=False)
            if user.id == self.user_id:
                return json.dumps({"error": "不能删除自己的账号"}, ensure_ascii=False)

            UserRepository.soft_delete(self.db, user)
            return json.dumps({
                "success": True,
                "message": f"用户 {user.name} 已被删除",
                "user_id": user_id,
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("admin_delete_user error: %s", e)
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def admin_approve_achievement(self, achievement_id: int, approve: bool = True) -> str:
        """
        审核成果。仅管理员可用。
        """
        if not self.is_admin:
            return json.dumps({"error": "仅管理员可审核成果"}, ensure_ascii=False)

        try:
            achievement = AchievementRepository.get_by_id(self.db, achievement_id)
            if not achievement:
                return json.dumps({"error": "成果不存在"}, ensure_ascii=False)

            status = "approved" if approve else "rejected"
            AchievementRepository.update_status(self.db, achievement, status)
            return json.dumps({
                "success": True,
                "message": f"成果 {achievement.title} 已{'通过' if approve else '拒绝'}审核",
                "achievement_id": achievement_id,
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("admin_approve_achievement error: %s", e)
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def admin_approve_resource(self, resource_id: int, approve: bool = True) -> str:
        """
        审核资源。仅管理员可用。
        """
        if not self.is_admin:
            return json.dumps({"error": "仅管理员可审核资源"}, ensure_ascii=False)

        try:
            ResourceRepository.update_status(self.db, resource_id, "approved" if approve else "rejected")
            return json.dumps({
                "success": True,
                "message": f"资源 ID:{resource_id} 已{'通过' if approve else '拒绝'}审核",
                "resource_id": resource_id,
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("admin_approve_resource error: %s", e)
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    # ========== 工具描述（供 Agent 系统提示使用） ==========

    @staticmethod
    def get_tools_description() -> str:
        """返回可用工具的描述，用于构建系统提示"""
        return """
## 可用工具

### 查询工具（所有用户可用）
1. **get_user_info(target_user_id, student_no)**: 查询用户信息。可通过用户ID或学号查询。
   - 权限：管理员可查任意用户；教师可查学生；其他人只能查自己
   
2. **list_users(role, status, page, page_size)**: 查询用户列表。
   - 权限：仅管理员可用
   
3. **count_users()**: 统计系统用户数量（按角色、状态分组）。
   - 权限：仅管理员可用
   
4. **list_achievements(user_id, status, category, q, page, page_size)**: 查询成果列表。
   - 权限：管理员/教师可查所有；其他人查公开或自己的
   
5. **list_resources(type, q, tag, page, page_size)**: 查询资源列表（仅已审核通过的）。
   - 权限：所有用户可用
   
6. **list_teachers(q, tag, page, page_size)**: 查询教师列表。
   - 权限：所有用户可用
   
7. **list_teacher_directions(teacher_id, active_only)**: 查询教师研究方向。
   - 权限：所有用户可用
   
8. **list_applications(status, page, page_size)**: 查询交流申请。
   - 权限：管理员查所有；教师查自己的；学生查自己的
   
9. **list_learning_plans(user_id, is_completed, page, page_size)**: 查询学习计划。
   - 权限：管理员可查所有；其他人只能查自己的
   
10. **list_notifications(page, page_size)**: 查询当前用户的通知。
    - 权限：仅自己的通知
    
11. **list_chat_sessions(page, page_size)**: 查询当前用户的聊天会话。
    - 权限：仅自己的会话
    
12. **get_platform_stats()**: 获取平台总体统计（用户数、成果数、资源数等）。
    - 权限：仅管理员可用

### 业务 Skill 工具
13. **recommend_competitions(user_input)**: 根据用户画像和自然语言条件推荐竞赛，并说明推荐理由。
    - 权限：所有登录用户；仅返回可推荐的已审核竞赛

14. **match_mentors(user_input)**: 根据项目描述匹配导师及有效研究方向。
    - 权限：所有登录用户；不会返回教师非公开联系方式

15. **query_party(user_input)**: 查询党建活动、本人党员信息或报名签到记录。
    - 权限：按党建模块权限；只读，党员名册和统计仅管理员可查

16. **manage_achievements(user_input)**: 查询或管理当前用户本人的成果。
    - 权限：仅限本人成果；新增、修改、删除只生成预览并等待确认

### 管理工具（仅管理员可用，执行前必须二次确认）
17. **admin_create_user(student_no, name, role, initial_password)**: 创建新用户。
    - 初始密码默认为 123456
    - 用户创建后状态为 pending_change（需首次登录改密）
    
18. **admin_reset_password(user_id, new_password)**: 重置用户密码。
    - 新密码默认为 123456
    - 用户重置后状态为 pending_change
    
19. **admin_update_user_status(user_id, status)**: 更新用户状态。
    - 可选状态：active, disabled, pending_change
    
20. **admin_delete_user(user_id)**: 软删除用户（标记为已删除）。
    - 不能删除自己的账号
    
21. **admin_approve_achievement(achievement_id, approve)**: 审核成果。
    - approve=True 通过，approve=False 拒绝
    
22. **admin_approve_resource(resource_id, approve)**: 审核资源。
    - approve=True 通过，approve=False 拒绝
"""

    @staticmethod
    def get_tool_list() -> list[str]:
        """返回所有工具名称列表"""
        return [
            "get_user_info", "list_users", "count_users",
            "list_achievements", "list_resources", "list_teachers",
            "list_teacher_directions", "list_applications",
            "list_learning_plans", "list_notifications",
            "list_chat_sessions", "get_platform_stats",
            "recommend_competitions", "match_mentors",
            "query_party", "manage_achievements",
            "list_party_members", "get_party_member", "list_party_activities",
            "get_party_activity", "get_party_my_records",
            "get_my_political_status", "list_political_learning_materials",
            "get_political_status_stats",
            "list_my_achievements", "get_my_achievement", "get_achievement_templates",
            "create_achievement", "update_achievement", "delete_achievement",
            "admin_create_user", "admin_reset_password",
            "admin_update_user_status", "admin_delete_user",
            "admin_approve_achievement", "admin_approve_resource",
        ]
