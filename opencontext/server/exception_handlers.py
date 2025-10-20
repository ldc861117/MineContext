# -*- coding: utf-8 -*-

# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
Centralized FastAPI exception handlers producing RFC7807 problem+json responses
with correlation ids and sanitized details.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from opencontext.utils.logging_utils import get_logger
from opencontext.utils import trace_context

logger = get_logger(__name__)


PROBLEM_JSON = "application/problem+json"


def _problem_response(status: int, title: str, detail: str, request: Request, type_: str = "about:blank", extra: Dict[str, Any] | None = None) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", None) or trace_context.get_trace_id()
    request_id = getattr(request.state, "request_id", None) or trace_context.get_request_id()
    body: Dict[str, Any] = {
        "type": type_,
        "title": title,
        "status": status,
        "detail": detail,
        "trace_id": trace_id,
        "request_id": request_id,
        "instance": str(request.url),
    }
    if extra:
        body.update(extra)
    return JSONResponse(status_code=status, content=body, media_type=PROBLEM_JSON)


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    # Sanitize message
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    logger.warning(f"HTTP error {exc.status_code}: {message}")
    return _problem_response(status=exc.status_code, title="HTTP Error", detail=message, request=request)


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Collect clean validation errors
    errors = [
        {
            "loc": e.get("loc"),
            "msg": e.get("msg"),
            "type": e.get("type"),
        }
        for e in exc.errors()
    ]
    logger.info("Request validation error", errors=errors)
    return _problem_response(
        status=422,
        title="Validation Error",
        detail="Request validation failed",
        request=request,
        extra={"errors": errors},
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    # Log once with full stacktrace
    logger.exception("Unhandled exception during request handling")
    # Do not leak internal error messages to clients
    return _problem_response(
        status=500,
        title="Internal Server Error",
        detail="An unexpected error occurred.",
        request=request,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
