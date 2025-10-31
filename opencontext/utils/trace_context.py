# -*- coding: utf-8 -*-

# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
Trace context utilities using contextvars to propagate correlation identifiers
across async tasks and (where possible) threads.

Provides helpers for trace_id, request_id and job_id.
"""

from __future__ import annotations

import contextvars
import os
import re
import uuid
from contextlib import contextmanager
from typing import Optional

# Context variables for correlation
_trace_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("trace_id", default=None)
_request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_id", default=None
)
_job_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("job_id", default=None)


def new_trace_id() -> str:
    """Generate a new trace id (lowercase 32-hex) compatible with W3C traceparent."""
    return uuid.uuid4().hex


def new_request_id() -> str:
    """Generate a new request id (lowercase 32-hex)."""
    # Use same format as trace_id for simplicity
    return uuid.uuid4().hex


def set_trace_id(trace_id: Optional[str]) -> Optional[str]:
    token = _trace_id_var.set(trace_id)
    return token  # type: ignore[return-value]


def get_trace_id() -> Optional[str]:
    return _trace_id_var.get()


def set_request_id(request_id: Optional[str]) -> Optional[str]:
    token = _request_id_var.set(request_id)
    return token  # type: ignore[return-value]


def get_request_id() -> Optional[str]:
    return _request_id_var.get()


def set_job_id(job_id: Optional[str]) -> Optional[str]:
    token = _job_id_var.set(job_id)
    return token  # type: ignore[return-value]


def get_job_id() -> Optional[str]:
    return _job_id_var.get()


@contextmanager
def contextualize(trace_id: Optional[str] = None, request_id: Optional[str] = None, job_id: Optional[str] = None):
    """Context manager to temporarily set correlation ids in the current context."""
    t_token = _trace_id_var.set(trace_id if trace_id is not None else _trace_id_var.get())
    r_token = _request_id_var.set(request_id if request_id is not None else _request_id_var.get())
    j_token = _job_id_var.set(job_id if job_id is not None else _job_id_var.get())
    try:
        yield
    finally:
        # Restore previous values
        _trace_id_var.reset(t_token)
        _request_id_var.reset(r_token)
        _job_id_var.reset(j_token)


_TRACEPARENT_RE = re.compile(r"^(?:[\da-f]{2})-([\da-f]{32})-([\da-f]{16})-(?:[\da-f]{2})$")


def parse_traceparent(header_value: Optional[str]) -> Optional[str]:
    """
    Parse a W3C traceparent header and extract the 32-hex trace id if valid.
    Returns None if not parseable.
    """
    if not header_value:
        return None
    m = _TRACEPARENT_RE.match(header_value.strip())
    if not m:
        return None
    trace_id = m.group(1)
    # Exclude invalid trace ids of all zeros as per spec
    if trace_id == "0" * 32:
        return None
    return trace_id
