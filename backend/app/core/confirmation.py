"""
任务执行确认机制

实现"预览→确认→执行"两阶段提交流程，满足需求文档 §3.1 要求：
"发布、发送和修改数据前必须由用户确认"

工作流程：
1. 用户请求执行操作（如发布资源、提交作业）
2. 系统生成确认令牌 + 预览摘要 → 返回给用户
3. 用户查看预览 → 确认执行 → 提交确认令牌
4. 系统验证令牌 → 执行操作

确认令牌使用 JWT 签名，5 分钟有效期，包含操作类型和数据哈希。
"""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import jwt, JWTError

from backend.app.core.config import settings


# 确认令牌有效期（分钟）
CONFIRMATION_EXPIRE_MINUTES = 5


class ConfirmationManager:
    """确认令牌管理器"""

    @staticmethod
    def _hash_data(data: Any) -> str:
        """计算请求数据的 SHA256 哈希"""
        data_str = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(data_str.encode("utf-8")).hexdigest()

    @staticmethod
    def create_confirmation(user_id: int, operation: str, data: Any) -> dict:
        """
        生成确认令牌

        Args:
            user_id: 用户 ID
            operation: 操作类型（如 "resource.create"）
            data: 请求数据（将计算哈希）

        Returns:
            {
                "confirmation_token": "...",
                "preview_hash": "...",
                "expires_at": "2026-08-04T12:00:00Z",
            }
        """
        data_hash = ConfirmationManager._hash_data(data)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=CONFIRMATION_EXPIRE_MINUTES)

        payload = {
            "type": "confirmation",
            "user_id": user_id,
            "operation": operation,
            "data_hash": data_hash,
            "exp": expires_at,
            "iat": datetime.now(timezone.utc),
        }

        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        return {
            "confirmation_token": token,
            "preview_hash": data_hash[:16] + "...",
            "expires_at": expires_at.isoformat(),
        }

    @staticmethod
    def verify_confirmation(token: str, user_id: int, operation: str, data: Any) -> dict:
        """
        验证确认令牌

        Args:
            token: 确认令牌
            user_id: 当前用户 ID
            operation: 操作类型
            data: 请求数据（用于验证哈希一致性）

        Returns:
            {"valid": True} 或 {"valid": False, "error": "..."}

        Raises:
            AppException: 令牌无效、过期、用户不匹配、数据不一致
        """
        from backend.app.core.errors import AppException

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        except JWTError as e:
            error_str = str(e).lower()
            if "expire" in error_str:
                raise AppException("CONFIRMATION_EXPIRED", "确认令牌已过期，请重新预览", 401)
            raise AppException("CONFIRMATION_INVALID", "确认令牌无效", 401)

        # 验证令牌类型
        if payload.get("type") != "confirmation":
            raise AppException("CONFIRMATION_INVALID", "令牌类型错误", 401)

        # 验证用户
        if payload.get("user_id") != user_id:
            raise AppException("CONFIRMATION_INVALID", "确认令牌不属于当前用户", 403)

        # 验证操作类型
        if payload.get("operation") != operation:
            raise AppException("CONFIRMATION_MISMATCH", f"操作类型不匹配（预期 {payload.get('operation')}）", 400)

        # 验证数据一致性
        expected_hash = payload.get("data_hash")
        actual_hash = ConfirmationManager._hash_data(data)
        if expected_hash != actual_hash:
            raise AppException("CONFIRMATION_MISMATCH", "数据已变更，请重新预览", 400)

        return {"valid": True}

    @staticmethod
    def build_preview(operation: str, data: dict, description: str = "") -> dict:
        """
        构建预览摘要（脱敏后展示给用户的数据摘要）

        Args:
            operation: 操作类型
            data: 原始请求数据
            description: 操作描述

        Returns:
            预览摘要（移除敏感字段）
        """
        # 脱敏：移除密码、token 等敏感字段
        sensitive_keys = {"password", "new_password", "old_password", "token", "api_key", "secret"}
        preview = {}
        for key, value in data.items():
            if key.lower() in sensitive_keys:
                preview[key] = "***"
            else:
                preview[key] = value

        return {
            "operation": operation,
            "description": description or operation,
            "data_preview": preview,
            "warning": "请确认以上内容无误后执行操作",
        }


# 需要确认的操作注册表
_CONFIRMABLE_OPERATIONS: dict[str, str] = {
    "resource.create": "发布资源",
    "resource.update": "更新资源",
    "resource.delete": "删除资源",
    "achievement.create": "创建成果",
    "achievement.update": "更新成果",
    "achievement.delete": "删除成果",
    "assignment.submit": "提交作业",
    "application.create": "提交交流申请",
    "plan.create": "创建学习计划",
}


def is_confirmable(operation: str) -> bool:
    """检查操作是否需要确认"""
    return operation in _CONFIRMABLE_OPERATIONS


def get_operation_description(operation: str) -> str:
    """获取操作的中文描述"""
    return _CONFIRMABLE_OPERATIONS.get(operation, operation)


def require_confirmation_token(
    operation: str,
    token: str | None,
    data: Any,
    user_id: int,
) -> dict:
    """Require and verify a confirmation token for a business write."""
    from backend.app.core.errors import AppException

    if not token:
        raise AppException("CONFIRMATION_REQUIRED", "该操作需要先预览并确认", 400)
    return ConfirmationManager.verify_confirmation(token, user_id, operation, data)
