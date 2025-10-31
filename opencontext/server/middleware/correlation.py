# -*- coding: utf-8 -*-

# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
ASGI middleware to inject and propagate correlation identifiers:
- request_id: unique per HTTP request
- trace_id: end-to-end trace identifier (reused from incoming headers if present)

Also binds correlation ids into Loguru context so logs include them.
"""

from __future__ import annotations

import uuid
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from opencontext.utils.logging_utils import get_logger
from opencontext.utils import trace_context

logger = get_logger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        # Extract or generate request_id
        req_id = request.headers.get("x-request-id") or trace_context.new_request_id()

        # Extract trace_id from W3C traceparent or X-Trace-Id header, or generate
        trace_id = (
            trace_context.parse_traceparent(request.headers.get("traceparent"))
            or request.headers.get("x-trace-id")
            or trace_context.new_trace_id()
        )

        # Stash on request.state
        request.state.request_id = req_id
        request.state.trace_id = trace_id

        # Bind to contextvars and loguru contextualize
        with trace_context.contextualize(trace_id=trace_id, request_id=req_id):
            # Also bind to logger extras for this task context
            with logger.contextualize(trace_id=trace_id, request_id=req_id):
                response = await call_next(request)

        # Add correlation headers in response
        response.headers["X-Request-Id"] = req_id
        response.headers["X-Trace-Id"] = trace_id
        return response
