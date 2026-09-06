from typing import Optional
from datetime import datetime, timezone

from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.app.models.chat import ChatSession, ChatMessage, ChatMessageCitation
from backend.app.core.pagination import normalize_page, normalize_page_size
from backend.app.core.database import local_now


class ChatRepository:
    @staticmethod
    def add_citations(db: Session, message: ChatMessage, citations: list[dict], *, scope: str, user_id: int) -> list[ChatMessageCitation]:
        """Persist normalized sources without allowing none-mode knowledge citations."""
        if scope == "none" and any(item.get("source_type") == "knowledge" for item in citations):
            raise ValueError("none scope cannot persist knowledge citations")
        rows: list[ChatMessageCitation] = []
        for rank, item in enumerate(citations, 1):
            source_type = str(item.get("source_type") or "knowledge")
            if source_type not in {"knowledge", "web", "system"}:
                raise ValueError("unsupported citation source type")
            row = ChatMessageCitation(
                message_id=message.id,
                source_type=source_type,
                scope=scope,
                user_id=user_id,
                document_id=item.get("file_id") or item.get("document_id"),
                document_name=item.get("file_name") or item.get("document_name"),
                source_title=item.get("title") or item.get("name"),
                source_url=item.get("url") or item.get("source_url"),
                matched_excerpt=item.get("preview") or item.get("matched_excerpt") or item.get("snippet"),
                rank=rank,
            )
            db.add(row)
            rows.append(row)
        if rows:
            db.commit()
            for row in rows:
                db.refresh(row)
        return rows
    @staticmethod
    def create_session(
        db: Session, user_id: int, title: str = "新会话", knowledge_scope: str = "personal", web_search_enabled: bool = True
    ) -> ChatSession:
        session = ChatSession(user_id=user_id, title=title, knowledge_scope=knowledge_scope, web_search_enabled=web_search_enabled)
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def get_session(db: Session, session_id: int, user_id: int) -> Optional[ChatSession]:
        return (
            db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == user_id, ChatSession.is_deleted.is_(False))
            .first()
        )

    @staticmethod
    def list_sessions(
        db: Session, user_id: int, page: int = 1, page_size: int = 20, q: Optional[str] = None
    ) -> tuple[list[ChatSession], int]:
        page = normalize_page(page)
        page_size = normalize_page_size(page_size)
        query = db.query(ChatSession).filter(
            ChatSession.user_id == user_id, ChatSession.is_deleted.is_(False)
        )
        if q:
            query = query.filter(ChatSession.title.ilike(f"%{q}%"))

        total = query.count()
        items = (
            query.order_by(desc(ChatSession.updated_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    @staticmethod
    def update_session(db: Session, session: ChatSession, title: str, knowledge_scope: Optional[str] = None, web_search_enabled: Optional[bool] = None) -> ChatSession:
        session.title = title
        if knowledge_scope is not None:
            session.knowledge_scope = knowledge_scope
        if web_search_enabled is not None:
            session.web_search_enabled = web_search_enabled
        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def delete_session(db: Session, session: ChatSession) -> ChatSession:
        session.is_deleted = True
        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def add_message(
        db: Session,
        session_id: int,
        role: str,
        content: str,
        skill_name: Optional[str] = None,
        token_usage: Optional[int] = None,
        duration_ms: Optional[int] = None,
        citations: Optional[str] = None,
        knowledge_scope: Optional[str] = None,
        request_id: Optional[str] = None,
        status: str = "completed",
        partial_content: Optional[str] = None,
    ) -> ChatMessage:
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            skill_name=skill_name,
            token_usage=token_usage,
            duration_ms=duration_ms,
            citations=citations,
            knowledge_scope=knowledge_scope,
            request_id=request_id,
            status=status,
            partial_content=partial_content,
        )
        db.add(msg)
        # 触发 updated_at 更新
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session:
            session.updated_at = local_now()
        db.commit()
        db.refresh(msg)
        return msg

    @staticmethod
    def list_messages(
        db: Session, session_id: int, page: int = 1, page_size: int = 50
    ) -> tuple[list[ChatMessage], int]:
        page = normalize_page(page)
        page_size = normalize_page_size(page_size)
        query = db.query(ChatMessage).filter(ChatMessage.session_id == session_id)
        total = query.count()
        items = (
            query.order_by(ChatMessage.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    @staticmethod
    def get_last_message_preview(db: Session, session_id: int) -> Optional[str]:
        msg = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(desc(ChatMessage.id))
            .first()
        )
        if not msg:
            return None
        return msg.content[:100] if msg.content else None

    @staticmethod
    def get_recent_messages(db: Session, session_id: int, limit: int = 10) -> list[ChatMessage]:
        return (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(desc(ChatMessage.id))
            .limit(limit)
            .all()
        )
