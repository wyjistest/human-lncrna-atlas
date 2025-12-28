"""
Security-focused exception handling utilities

This module provides sanitized exception handling to prevent information leakage
through error messages. Database errors, internal exceptions, and other sensitive
details are logged internally but never exposed to API clients.

Security best practices:
- Never expose raw database error messages to clients
- Generate unique error IDs for correlation between client reports and server logs
- Log full exception details with stack traces for debugging
- Return generic, user-friendly error messages to clients
"""
import uuid
import logging
from typing import Any, Dict, List

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError

from app.core.utils import sanitize_for_log


def _default_error_code_for_status(status_code: int) -> str:
    mapping = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        413: "REQUEST_BODY_TOO_LARGE",
        414: "QUERY_STRING_TOO_LONG",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMIT_EXCEEDED",
        500: "INTERNAL_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
        504: "GATEWAY_TIMEOUT",
    }
    if status_code in mapping:
        return mapping[status_code]
    if 400 <= status_code < 500:
        return "CLIENT_ERROR"
    if status_code >= 500:
        return "SERVER_ERROR"
    return "ERROR"


def normalize_http_error_detail(detail: Any, *, status_code: int) -> Dict[str, Any]:
    """
    Normalize FastAPI/Starlette error `detail` into a consistent object shape.

    Goal: make API error responses consistent for clients and reduce leakage risk
    (e.g., avoid returning raw validation inputs).

    Output shape:
      {"error": "<CODE>", "message": "<human-readable>", ...}
    """
    default_code = _default_error_code_for_status(status_code)

    # Fast path: already a dict-like detail from our code.
    if isinstance(detail, dict):
        error_code = detail.get("error")
        message = detail.get("message")

        # Preserve existing keys; fill missing ones.
        normalized: Dict[str, Any] = dict(detail)
        if not isinstance(error_code, str) or not error_code.strip():
            normalized["error"] = default_code
        if not isinstance(message, str) or not message.strip():
            # Try to derive a message from other fields.
            fallback = None
            for key in ("detail", "msg", "reason"):
                val = detail.get(key)
                if isinstance(val, str) and val.strip():
                    fallback = val
                    break
            normalized["message"] = fallback or normalized.get("error") or "Request failed"
        return normalized

    # Validation error lists should not echo raw input back to the client.
    if isinstance(detail, list):
        errors: List[Dict[str, Any]] = []
        for item in detail[:50]:
            if not isinstance(item, dict):
                continue
            errors.append(
                {
                    "loc": item.get("loc"),
                    "msg": item.get("msg"),
                    "type": item.get("type"),
                }
            )
        message = "Validation error"
        if errors:
            first_msg = errors[0].get("msg")
            if isinstance(first_msg, str) and first_msg.strip():
                message = first_msg
        return {"error": "VALIDATION_ERROR", "message": message, "errors": errors}

    # String / other types: coerce to a message string.
    message = str(detail) if detail is not None else "Request failed"
    return {"error": default_code, "message": message}


def build_validation_error_detail(exc: RequestValidationError) -> Dict[str, Any]:
    """
    Build a safe, consistent detail object for 422 RequestValidationError.

    SECURITY: Pydantic errors may include `input` values. We intentionally drop them.
    """
    try:
        raw_errors = exc.errors()
    except Exception:
        raw_errors = []
    return normalize_http_error_detail(raw_errors, status_code=422)


def sanitize_db_error(e: Exception, logger: logging.Logger) -> HTTPException:
    """
    Sanitize database errors - log details internally, return safe message to client.

    This function prevents information leakage by:
    1. Generating a unique error ID for tracking
    2. Logging the full error details (including stack trace) to server logs
    3. Returning a generic error message to the client with only the error ID

    The error ID allows support staff to correlate client-reported errors with
    server-side logs without exposing sensitive database details.

    Args:
        e: The caught exception (typically a database error)
        logger: Logger instance for recording the error details

    Returns:
        HTTPException with sanitized error details safe for client consumption

    Example:
        ```python
        try:
            result = db.execute(query)
        except Exception as e:
            raise sanitize_db_error(e, logger)
        ```

    Client receives:
        ```json
        {
            "detail": {
                "error": "DATABASE_ERROR",
                "message": "A database error occurred",
                "error_id": "a1b2c3d4"
            }
        }
        ```

    Server logs:
        ERROR - Database error [a1b2c3d4]: <full error message with traceback>
    """
    error_id = uuid.uuid4().hex[:8]
    # SECURITY: 防止日志注入/日志膨胀（异常消息可能包含控制字符或超长内容）
    safe_error = sanitize_for_log(e, max_length=2000)
    logger.error("Database error [%s]: %s", error_id, safe_error, exc_info=True)
    return HTTPException(
        status_code=500,
        detail={
            "error": "DATABASE_ERROR",
            "message": "A database error occurred",
            "error_id": error_id
        }
    )


def sanitize_internal_error(
    e: Exception,
    logger: logging.Logger,
    error_type: str = "INTERNAL_ERROR",
    message: str = "An internal error occurred"
) -> HTTPException:
    """
    Sanitize internal errors - log details internally, return safe message to client.

    Similar to sanitize_db_error but allows customization of the error type and message.
    Useful for non-database errors that still need sanitization.

    Args:
        e: The caught exception
        logger: Logger instance for recording the error details
        error_type: Error code to return to client (e.g., "VALIDATION_ERROR", "SERVICE_ERROR")
        message: User-friendly message to return to client

    Returns:
        HTTPException with sanitized error details safe for client consumption

    Example:
        ```python
        try:
            result = external_service.call()
        except ServiceError as e:
            raise sanitize_internal_error(e, logger, "SERVICE_ERROR", "External service unavailable")
        ```
    """
    error_id = uuid.uuid4().hex[:8]
    # SECURITY: 防止日志注入/日志膨胀（异常消息可能包含控制字符或超长内容）
    safe_error = sanitize_for_log(e, max_length=2000)
    logger.error("%s [%s]: %s", error_type, error_id, safe_error, exc_info=True)
    return HTTPException(
        status_code=500,
        detail={
            "error": error_type,
            "message": message,
            "error_id": error_id
        }
    )
