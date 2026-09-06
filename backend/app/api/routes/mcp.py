"""MCP 工具接口：供外部 Agent/工具调用，服务令牌鉴权 + SSRF 防护"""
import ipaddress
import logging
import os
import socket
import tempfile
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.core.errors import AppException
from backend.app.repositories.file_repo import FileRepository
from backend.app.ai.parser import parse_file

logger = logging.getLogger(__name__)
router = APIRouter()


# ========== 服务令牌鉴权 ==========
# 注意：使用 Header(None) 而非 Header(...)，缺失令牌时返回 401 而非 422
def require_service_token(x_service_token: str | None = Header(None, alias="X-Service-Token")):
    if not x_service_token or x_service_token != settings.MCP_SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="无效的服务令牌")
    return x_service_token


# ========== SSRF 防护 ==========
def _is_safe_url(url: str) -> tuple[bool, str]:
    """校验 URL 是否安全：仅 http/https，禁止内网/回环/链路本地地址"""
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "URL 解析失败"

    if parsed.scheme not in ("http", "https"):
        return False, f"不允许的协议: {parsed.scheme}"
    if not parsed.hostname:
        return False, "缺少主机名"

    hostname = parsed.hostname
    # 禁止localhost 类主机名
    if hostname.lower() in ("localhost", "localhost.localdomain"):
        return False, "禁止访问 localhost"

    # 解析所有 IP（含域名解析）
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False, f"无法解析主机名: {hostname}"

    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        # 禁止回环/私有/链路本地/保留地址
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False, f"禁止访问内网/保留地址: {ip_str}"
    return True, "ok"


# ========== 请求模型 ==========
class FetchPageRequest(BaseModel):
    url: str
    max_length: int = 20000


class SearchKnowledgeRequest(BaseModel):
    query: str
    scope: str = "personal"
    user_id: int | None = None
    limit: int = 5


class RenderMindmapRequest(BaseModel):
    content: str


# ========== 工具接口 ==========
@router.post("/parse-file")
async def mcp_parse_file(
    file: UploadFile = File(...),
    token: str = Depends(require_service_token),
):
    """解析上传的文件，返回切片结果"""
    if not file.filename:
        raise AppException("INVALID_FILE", "文件名为空", 400)
    # 写入临时文件后解析
    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        chunks = parse_file(tmp_path, file.filename)
        return {
            "filename": file.filename,
            "chunk_count": len(chunks),
            "chunks": [{"content": c["content"][:500], "page_no": c.get("page_no")} for c in chunks],
        }
    finally:
        os.unlink(tmp_path)


@router.post("/fetch-page")
async def mcp_fetch_page(
    req: FetchPageRequest,
    token: str = Depends(require_service_token),
):
    """抓取网页内容（SSRF 防护：仅公网 http/https）"""
    safe, msg = _is_safe_url(req.url)
    if not safe:
        raise AppException("SSF_BLOCKED", f"URL 不安全: {msg}", 400)

    try:
        async with httpx.AsyncClient(
            timeout=settings.MCP_FETCH_TIMEOUT,
            follow_redirects=False,  # 禁止跟随重定向（防止重定向到内网）
        ) as client:
            resp = await client.get(req.url, headers={"User-Agent": "LongMa-MCP/1.0"})
        if resp.status_code >= 400:
            raise AppException("FETCH_FAILED", f"抓取失败: HTTP {resp.status_code}", 502)
        text = resp.text[: req.max_length]
        return {
            "url": req.url,
            "status_code": resp.status_code,
            "content_type": resp.headers.get("content-type", ""),
            "length": len(text),
            "content": text,
        }
    except httpx.RequestError as e:
        raise AppException("FETCH_ERROR", f"请求异常: {e}", 502)


@router.post("/search-knowledge")
async def mcp_search_knowledge(
    req: SearchKnowledgeRequest,
    token: str = Depends(require_service_token),
    db: Session = Depends(get_db),
):
    """检索知识库切片"""
    results = FileRepository.search_chunks(
        db, query=req.query, scope=req.scope, user_id=req.user_id, limit=req.limit
    )
    return {"query": req.query, "count": len(results), "results": results}


@router.post("/render-mindmap")
async def mcp_render_mindmap(
    req: RenderMindmapRequest,
    token: str = Depends(require_service_token),
):
    """将 Markdown 文本渲染为思维导图树结构"""
    lines = [ln.rstrip() for ln in req.content.splitlines() if ln.strip()]
    root: dict[str, Any] = {"title": "思维导图", "children": []}
    # 用栈维护当前层级路径
    stack: list[tuple[int, dict[str, Any]]] = [(0, root)]
    for line in lines:
        # 计算标题层级（# 数量）
        level = 0
        stripped = line.lstrip()
        while stripped.startswith("#"):
            level += 1
            stripped = stripped[1:]
        title = stripped.strip()
        if not title:
            continue
        if level == 0:
            level = 1
        node = {"title": title, "children": []}
        # 找到父节点：栈顶层级 < 当前 level
        while len(stack) > 1 and stack[-1][0] >= level:
            stack.pop()
        stack[-1][1]["children"].append(node)
        stack.append((level, node))
    return {"tree": root}
