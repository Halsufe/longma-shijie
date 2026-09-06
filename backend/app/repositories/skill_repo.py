import json
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.app.models.skill import Skill, SkillCall
from backend.app.core.pagination import normalize_page, normalize_page_size


# 系统内置 Skill 种子数据
SYSTEM_SKILLS = [
    {
        "name": "mindmap",
        "display_name": "思维导图",
        "triggers": ["@思维导图", "@mindmap"],
        "description": "将内容整理为 Markdown 大纲格式的思维导图",
        "category": "text",
    },
    {
        "name": "translate",
        "display_name": "翻译",
        "triggers": ["@翻译", "@translate"],
        "description": "中英互译，自动检测语言",
        "category": "text",
    },
    {
        "name": "code_explain",
        "display_name": "代码解释",
        "triggers": ["@代码解释", "@explain"],
        "description": "解释代码逻辑、复杂度与风险",
        "category": "code",
    },
    {
        "name": "code_generate",
        "display_name": "代码生成",
        "triggers": ["@代码生成", "@writecode"],
        "description": "根据描述生成代码",
        "category": "code",
    },
    {
        "name": "summary",
        "display_name": "总结",
        "triggers": ["@总结", "@summary"],
        "description": "提炼核心要点并总结",
        "category": "text",
    },
    {
        "name": "polish",
        "display_name": "润色",
        "triggers": ["@润色", "@polish"],
        "description": "优化语言表达，提升流畅度",
        "category": "text",
    },
    {
        "name": "competition_recommend",
        "display_name": "竞赛推荐",
        "triggers": ["@竞赛推荐", "@比赛推荐", "@推荐比赛", "@competition"],
        "description": "结合学生画像与比赛库推荐适合的竞赛并说明理由",
        "category": "business",
    },
    {
        "name": "mentor_match",
        "display_name": "导师匹配",
        "triggers": ["@导师匹配", "@找导师", "@匹配导师", "@mentor"],
        "description": "根据项目描述匹配教师研究方向并说明理由",
        "category": "business",
    },
    {
        "name": "party_query",
        "display_name": "党建查询",
        "triggers": ["@党建查询", "@党建", "@党员查询", "@party"],
        "description": "按现有党建权限查询党员、活动和本人参与记录",
        "category": "business",
    },
    {
        "name": "achievement_manage",
        "display_name": "成果管理",
        "triggers": ["@成果管理", "@我的成果", "@成果录入", "@achievement"],
        "description": "查询和管理本人成果，写操作必须经过任务确认",
        "category": "business",
    },
]


class SkillRepository:
    @staticmethod
    def seed_system_skills(db: Session) -> int:
        """首次启动时写入内置 Skill，返回新增数量"""
        created = 0
        for s in SYSTEM_SKILLS:
            existing = db.query(Skill).filter(Skill.name == s["name"]).first()
            if not existing:
                skill = Skill(
                    name=s["name"],
                    display_name=s["display_name"],
                    triggers=json.dumps(s["triggers"], ensure_ascii=False),
                    description=s["description"],
                    category=s["category"],
                    is_enabled=True,
                    is_system=True,
                )
                db.add(skill)
                created += 1
        db.commit()
        return created

    @staticmethod
    def get_by_name(db: Session, name: str) -> Optional[Skill]:
        return db.query(Skill).filter(Skill.name == name).first()

    @staticmethod
    def get_by_id(db: Session, skill_id: int) -> Optional[Skill]:
        return db.query(Skill).filter(Skill.id == skill_id).first()

    @staticmethod
    def list(db: Session, is_enabled: Optional[bool] = None) -> list[Skill]:
        query = db.query(Skill)
        if is_enabled is not None:
            query = query.filter(Skill.is_enabled == is_enabled)
        return query.order_by(Skill.id).all()

    @staticmethod
    def update(db: Session, skill: Skill, **kwargs) -> Skill:
        for k, v in kwargs.items():
            if k == "triggers" and isinstance(v, list):
                v = json.dumps(v, ensure_ascii=False)
            if hasattr(skill, k) and v is not None:
                setattr(skill, k, v)
        db.commit()
        db.refresh(skill)
        return skill

    @staticmethod
    def get_triggers_map(db: Session) -> dict[str, str]:
        """返回 {触发词: skill_name}（仅启用的）"""
        skills = db.query(Skill).filter(Skill.is_enabled.is_(True)).order_by(Skill.id).all()
        mapping: dict[str, str] = {}
        for s in skills:
            try:
                triggers = json.loads(s.triggers) if s.triggers else []
            except (json.JSONDecodeError, TypeError):
                triggers = []
            for t in triggers:
                mapping.setdefault(t, s.name)
        return mapping


class SkillCallRepository:
    @staticmethod
    def create(
        db: Session,
        skill_name: str,
        user_id: Optional[int],
        input: str,
        output: Optional[str] = None,
        status: str = "success",
        duration_ms: Optional[int] = None,
        token_usage: Optional[int] = None,
        error: Optional[str] = None,
    ) -> SkillCall:
        call = SkillCall(
            skill_name=skill_name,
            user_id=user_id,
            input=input,
            output=output,
            status=status,
            duration_ms=duration_ms,
            token_usage=token_usage,
            error=error,
        )
        db.add(call)
        db.commit()
        db.refresh(call)
        return call

    @staticmethod
    def list(
        db: Session,
        skill_name: Optional[str] = None,
        user_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SkillCall], int]:
        page = normalize_page(page)
        page_size = normalize_page_size(page_size)
        query = db.query(SkillCall)
        if skill_name:
            query = query.filter(SkillCall.skill_name == skill_name)
        if user_id:
            query = query.filter(SkillCall.user_id == user_id)
        total = query.count()
        items = (
            query.order_by(desc(SkillCall.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total
