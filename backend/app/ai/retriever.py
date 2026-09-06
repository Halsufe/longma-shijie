import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from backend.app.repositories.file_repo import FileRepository
from backend.app.repositories.user_repo import UserRepository
from backend.app.services.knowledge_scope import KnowledgeScopeGuard

logger = logging.getLogger(__name__)


class RAGService:
    """RAG 检索服务：先权限过滤，再检索"""

    @staticmethod
    def search(
        db: Session,
        query: str,
        scope: str = "personal",
        user_id: Optional[int] = None,
        limit: int = 5,
    ) -> list[dict]:
        """
        检索知识库
        scope: personal / class / all
        返回: [{"file_id", "file_name", "chunk_content", "page_no", "score"}]
        """
        if scope not in ("personal", "class", "none"):
            raise ValueError("knowledge scope must be personal, class, or none")
        if scope == "none":
            return []
        user = UserRepository.get_by_id(db, user_id) if user_id is not None else None
        if user is None:
            raise PermissionError("当前用户不存在")
        context = KnowledgeScopeGuard.authorize(db, user, scope)
        results = FileRepository.search_chunks(
            db, query=query, scope=scope, user_id=user_id,
            class_id=context.class_id, limit=limit
        )
        logger.info("RAG search: query='%s' scope=%s results=%d", query[:50], scope, len(results))
        return results

    @staticmethod
    def build_context(results: list[dict]) -> str:
        """将检索结果构建为 Prompt 上下文"""
        if not results:
            return ""

        context_parts = []
        for i, r in enumerate(results, 1):
            page_info = f"（第{r['page_no']}页）" if r.get("page_no") else ""
            context_parts.append(
                f"[来源{i}] {r['file_name']}{page_info}\n{r['chunk_content']}"
            )

        return "\n\n".join(context_parts)

    @staticmethod
    def build_rag_prompt(query: str, context: str) -> str:
        """构建 RAG 系统提示词"""
        if not context:
            return ""

        return (
            f"以下是从知识库中检索到的相关资料，请基于这些资料回答用户问题。"
            f"如果资料中没有相关信息，请说明并基于你的知识回答。\n\n"
            f"=== 知识库资料 ===\n{context}\n=== 资料结束 ===\n\n"
            f"请在回答中标注引用来源（如 [来源1]）。"
        )

    @staticmethod
    def format_citations(results: list[dict]) -> Optional[str]:
        """格式化引用来源为 JSON 字符串（存入消息 citations 字段）"""
        if not results:
            return None

        citations = []
        for r in results:
            citations.append({
                "file_id": r["file_id"],
                "file_name": r["file_name"],
                "page_no": r.get("page_no"),
                "preview": r["chunk_content"][:200],
            })
        return json.dumps(citations, ensure_ascii=False)
