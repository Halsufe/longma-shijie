"""Chat attachment facade kept separate from the chat route for reuse and testing."""

from collections.abc import Sequence
from typing import Any

from fastapi import UploadFile
from sqlalchemy.orm import Session

from backend.app.services.chat_service import ChatService


class ChatAttachmentService:
    """Persist chat files and return bounded text that can be used as context."""

    @staticmethod
    async def save(
        db: Session, message_id: int, user_id: int, files: Sequence[UploadFile]
    ) -> tuple[list[dict[str, Any]], str]:
        return await ChatService.save_attachments(db, message_id, user_id, files)

