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
from fastapi import HTTPException


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
    logger.error(f"Database error [{error_id}]: {str(e)}", exc_info=True)
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
    logger.error(f"{error_type} [{error_id}]: {str(e)}", exc_info=True)
    return HTTPException(
        status_code=500,
        detail={
            "error": error_type,
            "message": message,
            "error_id": error_id
        }
    )
