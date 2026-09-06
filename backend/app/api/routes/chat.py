import json
import logging
import uuid
from typing import cast

from fastapi import APIRouter, Depends, Query, Request, UploadFile
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.database import local_now
from backend.app.core.errors import AppException
from backend.app.repositories.chat_repo import ChatRepository
from backend.app.schemas.chat import (
    SessionCreate,
    SessionUpdate,
    SessionInfo,
    SessionListResponse,
    MessageInfo,
    MessageListResponse,
    MessageSend,
)
from backend.app.api.deps import get_current_user
from backend.app.services.chat_service import ChatService
from backend.app.core.storage import StorageService
from backend.app.services.file_preview_service import FilePreviewService
from backend.app.services.knowledge_scope import KnowledgeScopeGuard, InvalidKnowledgeScope
from backend.app.models.chat_request import ChatRequest
from backend.app.core.config import settings
from backend.app.services.chat_quota_service import ChatQuotaService

logger = logging.getLogger(__name__)
router = APIRouter()


def _session_to_info(session, db: Session) -> SessionInfo:
    preview = ChatRepository.get_last_message_preview(db, session.id)
    return SessionInfo(
        id=session.id,
        user_id=session.user_id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        last_message_preview=preview,
        knowledge_scope=getattr(session, "knowledge_scope", "personal"),
        web_search_enabled=getattr(session, "web_search_enabled", True),
        last_message_status=getattr(session, "last_message_status", None),
    )


@router.post("/sessions", response_model=SessionInfo)
async def create_session(
    form: SessionCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    title = form.title or "新会话"
    try:
        KnowledgeScopeGuard.authorize(db, current_user, form.knowledge_scope, web_search_enabled=form.web_search_enabled)
    except PermissionError as exc:
        raise AppException("KNOWLEDGE_SCOPE_FORBIDDEN", str(exc), 403) from exc
    session = ChatRepository.create_session(
        db, user_id=current_user.id, title=title,
        knowledge_scope=form.knowledge_scope,
        web_search_enabled=form.web_search_enabled,
    )
    return SessionInfo(
        id=session.id,
        user_id=session.user_id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        last_message_preview=None,
        knowledge_scope=session.knowledge_scope,
        web_search_enabled=session.web_search_enabled,
        last_message_status=session.last_message_status,
    )


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),  # 上限由 normalize_page_size 静默截断到 100
    q: str = Query(None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items, total = ChatRepository.list_sessions(db, user_id=current_user.id, page=page, page_size=page_size, q=q)
    return SessionListResponse(
        total=total,
        items=[_session_to_info(s, db) for s in items],
    )


@router.get("/sessions/{session_id}", response_model=SessionInfo)
async def get_session(
    session_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = ChatRepository.get_session(db, session_id, current_user.id)
    if not session:
        raise AppException("SESSION_NOT_FOUND", "会话不存在", 404)
    return _session_to_info(session, db)


@router.put("/sessions/{session_id}", response_model=SessionInfo)
async def rename_session(
    session_id: int,
    form: SessionUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = ChatRepository.get_session(db, session_id, current_user.id)
    if not session:
        raise AppException("SESSION_NOT_FOUND", "会话不存在", 404)
    session = ChatRepository.update_session(db, session, form.title, form.knowledge_scope, form.web_search_enabled)
    return _session_to_info(session, db)


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = ChatRepository.get_session(db, session_id, current_user.id)
    if not session:
        raise AppException("SESSION_NOT_FOUND", "会话不存在", 404)
    ChatRepository.delete_session(db, session)
    return {"message": "会话已删除"}


@router.get("/sessions/{session_id}/messages", response_model=MessageListResponse)
async def list_messages(
    session_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = ChatRepository.get_session(db, session_id, current_user.id)
    if not session:
        raise AppException("SESSION_NOT_FOUND", "会话不存在", 404)
    items, total = ChatRepository.list_messages(db, session_id, page=page, page_size=page_size)
    return MessageListResponse(total=total, items=[MessageInfo.model_validate(m) for m in items])


@router.post("/sessions/{session_id}/messages")
async def send_message_stream(
    session_id: int,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """流式发送消息（SSE）"""
    session = ChatRepository.get_session(db, session_id, current_user.id)
    if not session:
        raise AppException("SESSION_NOT_FOUND", "会话不存在", 404)

    content_type = request.headers.get("content-type", "")
    attachments: list[UploadFile] = []
    if content_type.startswith("multipart/form-data"):
        form_data = await request.form()
        form = MessageSend(
            content=str(form_data.get("content") or ""),
            skill=None,
            rag_scope=str(form_data.get("rag_scope") or "personal"),
            idempotency_key=str(form_data.get("idempotency_key") or "") or None,
        )
        attachments = cast(list[UploadFile], [item for item in form_data.getlist("files") if hasattr(item, "filename") and hasattr(item, "file")])
    else:
        form = MessageSend.model_validate(await request.json())

    try:
        requested_scope = form.knowledge_scope or ("personal" if form.rag_scope == "all" else form.rag_scope)
        scope = KnowledgeScopeGuard.parse(requested_scope).value
        KnowledgeScopeGuard.authorize(db, current_user, scope, web_search_enabled=form.web_search_enabled)
    except InvalidKnowledgeScope as exc:
        raise AppException("INVALID_KNOWLEDGE_SCOPE", str(exc), 400) from exc
    except PermissionError as exc:
        raise AppException("KNOWLEDGE_SCOPE_FORBIDDEN", str(exc), 403) from exc
    lock = ChatService.session_lock(session_id)
    if lock.locked():
        raise AppException("CHAT_BUSY", "会话正在生成回复，请稍后再试", 409)

    request_id = str(uuid.uuid4())
    idempotency_key = form.idempotency_key or request.headers.get("Idempotency-Key") or request_id
    existing_request = db.query(ChatRequest).filter(
        ChatRequest.user_id == current_user.id, ChatRequest.idempotency_key == idempotency_key
    ).first()
    if existing_request:
        if existing_request.status in {"pending", "generating", "retrying"}:
            raise AppException("REQUEST_IN_PROGRESS", "请求正在生成，请稍后查询状态", 409)
        request_id = existing_request.request_id
    else:
        db.add(ChatRequest(
            request_id=request_id, session_id=session_id, user_id=current_user.id,
            idempotency_key=idempotency_key, model="deepseek-v4-flash", knowledge_scope=scope,
            input_content=form.content,
            status="pending", created_at=local_now(), updated_at=local_now(),
        ))
        db.commit()

    reservation = 0
    usage_key = f"{request_id}:attempt:1"
    if not existing_request and ChatQuotaService.effective_quota(db, current_user) > 0:
        reservation = max(0, settings.CHAT_MAX_RESERVATION_TOKENS)
        try:
            ChatQuotaService.reserve_request(
                db, current_user, request_id=request_id,
                reservation=reservation, idempotency_key=usage_key,
            )
        except ValueError as exc:
            raise AppException(str(exc), "今日 Token 额度不足", 429) from exc

    async def event_generator():
        await lock.acquire()
        actual_usage = None
        attempt_count = 1
        try:
            event_no = 0
            request_row = db.query(ChatRequest).filter(ChatRequest.request_id == request_id).first()
            if request_row:
                request_row.status = "generating"
                db.commit()
            async for event in ChatService.send_message_stream(
                db, session_id, form.content, current_user.id, rag_scope=scope, attachments=attachments
            ):
                event_no += 1
                event = {**event, "request_id": request_id, "event_id": event_no}
                if request_row:
                    request_row.last_event_id = event_no
                    request_row.partial_content = str(event.get("data") or "") if event.get("type") == "chunk" else request_row.partial_content
                    if event.get("type") in {"done", "request.completed"}:
                        request_row.status = "completed"
                        data = event.get("data")
                        if isinstance(data, dict):
                            actual_usage = data.get("usage")
                            attempt_count = max(1, int(data.get("attempt_count") or 1))
                            request_row.usage_status = "available" if actual_usage else "pending_reconciliation"
                    elif event.get("type") in {"error", "request.failed"}:
                        request_row.status = "failed"
                        request_row.error_code = event.get("error_code") or "AI_REQUEST_FAILED"
                        request_row.error_message = str(event.get("data") or "AI 请求失败")
                    db.commit()
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("Stream error")
            request_row = db.query(ChatRequest).filter(ChatRequest.request_id == request_id).first()
            if request_row:
                request_row.status = "failed"
                request_row.error_code = "STREAM_ERROR"
                request_row.error_message = str(e)
                db.commit()
            yield f"data: {json.dumps({'type': 'error', 'data': str(e), 'request_id': request_id}, ensure_ascii=False)}\n\n"
        finally:
            if reservation:
                try:
                    if attempt_count == 1:
                        ChatQuotaService.settle_request(
                            db, current_user, request_id=request_id,
                            reservation=reservation,
                            input_tokens=(actual_usage or {}).get("prompt_tokens") if isinstance(actual_usage, dict) else None,
                            output_tokens=(actual_usage or {}).get("completion_tokens") if isinstance(actual_usage, dict) else None,
                            idempotency_key=usage_key,
                        )
                    else:
                        ChatQuotaService.settle_request(
                            db, current_user, request_id=request_id,
                            reservation=reservation, input_tokens=None, output_tokens=None,
                            idempotency_key=usage_key,
                        )
                        for attempt_no in range(2, attempt_count):
                            ChatQuotaService.record_unmetered_attempt(
                                db, current_user, request_id=request_id, attempt_no=attempt_no,
                                idempotency_key=f"{request_id}:attempt:{attempt_no}",
                            )
                        ChatQuotaService.settle_request(
                            db, current_user, request_id=request_id, reservation=0,
                            input_tokens=(actual_usage or {}).get("prompt_tokens") if isinstance(actual_usage, dict) else None,
                            output_tokens=(actual_usage or {}).get("completion_tokens") if isinstance(actual_usage, dict) else None,
                            idempotency_key=f"{request_id}:attempt:{attempt_count}",
                            attempt_no=attempt_count,
                        )
                except Exception:
                    logger.exception("Token usage settlement failed: request_id=%s", request_id)
            lock.release()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/requests/{request_id}")
async def get_chat_request(request_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    request_row = db.query(ChatRequest).filter(
        ChatRequest.request_id == request_id, ChatRequest.user_id == current_user.id
    ).first()
    if not request_row:
        raise AppException("REQUEST_NOT_FOUND", "请求不存在", 404)
    return {
        "request_id": request_row.request_id,
        "session_id": request_row.session_id,
        "message_id": request_row.message_id,
        "status": request_row.status,
        "model": "deepseek-v4-flash",
        "knowledge_scope": request_row.knowledge_scope,
        "last_event_id": request_row.last_event_id,
        "retry_count": request_row.retry_count,
        "partial_content": request_row.partial_content,
        "usage_status": request_row.usage_status,
        "error_code": request_row.error_code,
    }


async def _recover_request(request_id: str, *, continue_generation: bool, current_user, db: Session):
    parent = db.query(ChatRequest).filter(
        ChatRequest.request_id == request_id, ChatRequest.user_id == current_user.id
    ).first()
    if not parent:
        raise AppException("REQUEST_NOT_FOUND", "请求不存在", 404)
    allowed = {"interrupted"} if continue_generation else {"failed"}
    if parent.status not in allowed:
        raise AppException("REQUEST_RECOVERY_NOT_ALLOWED", "当前请求状态不支持此操作", 409)
    if continue_generation and not parent.partial_content:
        raise AppException("REQUEST_RECOVERY_NOT_ALLOWED", "中断请求没有可继续的部分内容", 409)
    session_lock = ChatService.session_lock(parent.session_id)
    if session_lock.locked():
        raise AppException("REQUEST_IN_PROGRESS", "会话正在生成回复", 409)
    child_id = str(uuid.uuid4())
    child = ChatRequest(
        request_id=child_id, session_id=parent.session_id, user_id=current_user.id,
        parent_request_id=parent.request_id, idempotency_key=f"{child_id}:manual",
        model="deepseek-v4-flash", knowledge_scope=parent.knowledge_scope,
        input_content=parent.input_content or "继续生成",
        status="pending", created_at=local_now(), updated_at=local_now(),
    )
    db.add(child)
    db.commit()
    reservation = 0
    usage_key = f"{child_id}:attempt:1"
    if ChatQuotaService.effective_quota(db, current_user) > 0:
        reservation = max(0, settings.CHAT_MAX_RESERVATION_TOKENS)
        try:
            ChatQuotaService.reserve_request(
                db, current_user, request_id=child_id,
                reservation=reservation, idempotency_key=usage_key,
            )
        except ValueError as exc:
            child.status = "failed"
            child.error_code = str(exc)
            db.commit()
            raise AppException(str(exc), "今日 Token 额度不足", 429) from exc

    usage = None
    attempt_count = 1
    try:
        async with session_lock:
            child.status = "generating"
            db.commit()
            content = child.input_content
            if continue_generation:
                content = f"请从以下已生成内容之后继续回答，不要重复前文：\n{parent.partial_content}\n\n原问题：{content}"
            result = await ChatService.send_message_simple(
                db, parent.session_id, content or "继续生成", current_user.id,
                rag_scope=parent.knowledge_scope,
            )
            usage = result.get("ai_message", {}).get("usage")
            attempt_count = max(1, int(result.get("ai_message", {}).get("attempt_count") or 1))
        child.status = "completed"
        child.usage_status = "available" if usage else "pending_reconciliation"
        db.commit()
        return {"request_id": child_id, "parent_request_id": parent.request_id, "status": child.status, "result": result}
    except Exception as exc:
        child.status = "failed"
        child.error_code = "RECOVERY_FAILED"
        child.error_message = str(exc)
        db.commit()
        raise
    finally:
        if reservation:
            if attempt_count == 1:
                ChatQuotaService.settle_request(
                    db, current_user, request_id=child_id, reservation=reservation,
                    input_tokens=usage.get("prompt_tokens") if isinstance(usage, dict) else None,
                    output_tokens=usage.get("completion_tokens") if isinstance(usage, dict) else None,
                    idempotency_key=usage_key,
                )
            else:
                ChatQuotaService.settle_request(
                    db, current_user, request_id=child_id, reservation=reservation,
                    input_tokens=None, output_tokens=None, idempotency_key=usage_key,
                )
                for attempt_no in range(2, attempt_count):
                    ChatQuotaService.record_unmetered_attempt(
                        db, current_user, request_id=child_id, attempt_no=attempt_no,
                        idempotency_key=f"{child_id}:attempt:{attempt_no}",
                    )
                ChatQuotaService.settle_request(
                    db, current_user, request_id=child_id, reservation=0,
                    input_tokens=usage.get("prompt_tokens") if isinstance(usage, dict) else None,
                    output_tokens=usage.get("completion_tokens") if isinstance(usage, dict) else None,
                    idempotency_key=f"{child_id}:attempt:{attempt_count}",
                    attempt_no=attempt_count,
                )


@router.post("/requests/{request_id}/retry")
async def retry_chat_request(request_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return await _recover_request(request_id, continue_generation=False, current_user=current_user, db=db)


@router.post("/requests/{request_id}/continue")
async def continue_chat_request(request_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return await _recover_request(request_id, continue_generation=True, current_user=current_user, db=db)


@router.post("/sessions/{session_id}/messages/simple")
async def send_message_simple(
    session_id: int,
    form: MessageSend,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """非流式发送消息，返回完整回复"""
    session = ChatRepository.get_session(db, session_id, current_user.id)
    if not session:
        raise AppException("SESSION_NOT_FOUND", "会话不存在", 404)
    try:
        requested_scope = form.knowledge_scope or ("personal" if form.rag_scope == "all" else form.rag_scope)
        scope = KnowledgeScopeGuard.parse(requested_scope).value
        KnowledgeScopeGuard.authorize(db, current_user, scope, web_search_enabled=form.web_search_enabled)
    except InvalidKnowledgeScope as exc:
        raise AppException("INVALID_KNOWLEDGE_SCOPE", str(exc), 400) from exc
    except PermissionError as exc:
        raise AppException("KNOWLEDGE_SCOPE_FORBIDDEN", str(exc), 403) from exc
    lock = ChatService.session_lock(session_id)
    if lock.locked():
        raise AppException("CHAT_BUSY", "会话正在生成回复，请稍后再试", 409)
    async with lock:
        result = await ChatService.send_message_simple(
            db, session_id, form.content, current_user.id, rag_scope=scope
        )
    return result


@router.post("/sessions/{session_id}/messages/{message_id}/regenerate")
async def regenerate_message(
    session_id: int, message_id: int, request: Request, stream: bool = Query(False), current_user=Depends(get_current_user), db: Session = Depends(get_db),
):
    session = ChatRepository.get_session(db, session_id, current_user.id)
    if not session:
        raise AppException("SESSION_NOT_FOUND", "会话不存在", 404)
    lock = ChatService.session_lock(session_id)
    if lock.locked():
        raise AppException("CHAT_BUSY", "会话正在生成回复，请稍后再试", 409)
    async def generate():
        async with lock:
            message = await ChatService.regenerate_message(db, session_id, message_id, current_user.id)
        yield f"data: {json.dumps({'type': 'done', 'data': MessageInfo.model_validate(message).model_dump(mode='json')}, ensure_ascii=False)}\n\n"

    if stream or "text/event-stream" in request.headers.get("accept", ""):
        return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
    async with lock:
        message = await ChatService.regenerate_message(db, session_id, message_id, current_user.id)
    return MessageInfo.model_validate(message)


@router.get("/messages/{message_id}/attachments")
async def list_message_attachments(message_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    from backend.app.models.chat import ChatMessage, ChatMessageAttachment
    message = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
    if not message:
        raise AppException("MESSAGE_NOT_FOUND", "消息不存在", 404)
    session = ChatRepository.get_session(db, message.session_id, current_user.id)
    if not session:
        raise AppException("FORBIDDEN", "无权访问该消息", 403)
    rows = db.query(ChatMessageAttachment).filter(ChatMessageAttachment.message_id == message_id, ChatMessageAttachment.owner_user_id == current_user.id).all()
    return [{"id": row.id, "original_name": row.original_name, "mime_type": row.mime_type, "size": row.size} for row in rows]


@router.get("/attachments/{attachment_id}/download")
@router.get("/attachments/{attachment_id}/preview")
async def message_attachment_file(attachment_id: int, request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    from backend.app.models.chat import ChatMessage, ChatMessageAttachment
    row = db.query(ChatMessageAttachment).filter(ChatMessageAttachment.id == attachment_id, ChatMessageAttachment.owner_user_id == current_user.id).first()
    if not row:
        raise AppException("ATTACHMENT_NOT_FOUND", "附件不存在", 404)
    message = db.query(ChatMessage).filter(ChatMessage.id == row.message_id).first()
    if not message or not ChatRepository.get_session(db, message.session_id, current_user.id):
        raise AppException("FORBIDDEN", "无权访问附件", 403)
    path = StorageService.get_file_path("chat", current_user.id, row.stored_name)
    if request.url.path.endswith("/preview"):
        result = FilePreviewService.preview(path=path, original_name=row.original_name, stored_name=row.stored_name, mime_type=row.mime_type, size=row.size, scope="chat", user_id=current_user.id)
        if result.get("format") == "html":
            return HTMLResponse(result.get("content") or "", media_type="text/html")
        if result.get("format") == "inline":
            preview_path = result.get("preview_url") or path
            return FileResponse(preview_path, filename=row.original_name, media_type=result.get("mime_type") or row.mime_type, headers={"Content-Disposition": f"inline; filename*=UTF-8''{row.original_name}"})
        return {"supported": False, "message": result.get("message", "暂不支持预览，请下载查看")}
    return FileResponse(path, filename=row.original_name, media_type=row.mime_type)


@router.get("/agent/status")
async def get_agent_status(
    current_user=Depends(get_current_user),
):
    """获取当前用户的 Agent 状态（记忆统计、待确认操作等）"""
    from backend.app.services.chat_service import _agent_sessions, _agent_memories

    user_id = current_user.id
    memory = _agent_memories.get(user_id)
    agent = _agent_sessions.get(user_id)

    if not memory:
        return {
            "enabled": True,
            "user_id": user_id,
            "memory": {
                "conversation_messages": 0,
                "cached_tool_calls": 0,
                "remembered_facts": 0,
            },
            "pending_confirmations": [],
            "triggers": list({"@agent", "@智能", "@助手", "@ai"}),
        }

    memory_stats = {
        "conversation_messages": len(memory.conversation_history),
        "cached_tool_calls": len(memory.tool_call_cache),
        "remembered_facts": len(memory.fact_memory),
    }

    pending = []
    if agent:
        pending = agent.get_confirmation_status()

    return {
        "enabled": True,
        "user_id": user_id,
        "memory": memory_stats,
        "pending_confirmations": pending,
        "triggers": list({"@agent", "@智能", "@助手", "@ai"}),
    }


@router.post("/agent/clear-memory")
async def clear_agent_memory(
    current_user=Depends(get_current_user),
):
    """清空当前用户的 Agent 记忆"""
    from backend.app.services.chat_service import _agent_sessions, _agent_memories

    user_id = current_user.id
    memory = _agent_memories.get(user_id)
    agent = _agent_sessions.get(user_id)

    if memory:
        memory.clear()
    if agent:
        agent.cancel_all_confirmations()

    return {"message": "Agent 记忆已清空", "user_id": user_id}
