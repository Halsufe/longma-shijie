from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

import uuid
import logging

logger = logging.getLogger(__name__)


class AppException(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code


def _build_error_response(code: str, message: str, status_code: int, request_id: str):
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {"code": code, "message": message},
            "request_id": request_id,
        },
    )


def register_exception_handlers(app):
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        logger.warning(
            "AppException: code=%s message=%s request_id=%s",
            exc.code, exc.message, request_id,
        )
        return _build_error_response(exc.code, exc.message, exc.status_code, request_id)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        errors = exc.errors()
        messages = []
        for err in errors:
            loc = " -> ".join(str(l) for l in err.get("loc", []))
            msg = err.get("msg", "")
            messages.append(f"{loc}: {msg}" if loc else msg)
        return _build_error_response(
            "VALIDATION_ERROR",
            "; ".join(messages) if messages else "参数校验失败",
            422,
            request_id,
        )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return _build_error_response("NOT_FOUND", "资源不存在", 404, request_id)

    @app.exception_handler(401)
    async def unauthorized_handler(request: Request, exc):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return _build_error_response("UNAUTHORIZED", "未授权", 401, request_id)

    @app.exception_handler(403)
    async def forbidden_handler(request: Request, exc):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return _build_error_response("FORBIDDEN", "无权限", 403, request_id)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        logger.exception(
            "Unhandled exception: request_id=%s error=%s", request_id, str(exc)
        )
        return _build_error_response(
            "INTERNAL_ERROR", "服务器内部错误", 500, request_id
        )