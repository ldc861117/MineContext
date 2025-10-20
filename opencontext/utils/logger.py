#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0


"""
Log manager for configuring and managing logging
- Emits JSON logs with correlation ids by default
- Supports pretty console logs in development via config or env
- Redacts sensitive data by default
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from typing import Any, Dict, Optional

from loguru import logger

from opencontext.utils import trace_context


_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_BEARER_RE = re.compile(r"(Bearer)\s+[A-Za-z0-9\-._~+/]+=*")
_SECRET_KEYS = {"password", "passwd", "secret", "token", "access_token", "refresh_token", "api_key", "apikey", "authorization", "cookie", "set-cookie", "email"}


def _to_iso8601(dt: datetime) -> str:
    try:
        return dt.isoformat()
    except Exception:
        # Fallback to string formatting
        return dt.strftime("%Y-%m-%dT%H:%M:%S%z")


def _redact_str(s: str) -> str:
    if not s:
        return s
    s = _EMAIL_RE.sub("<redacted_email>", s)
    s = _BEARER_RE.sub(r"\1 <redacted_token>", s)
    return s


def _redact_obj(obj: Any) -> Any:
    try:
        if isinstance(obj, str):
            return _redact_str(obj)
        if isinstance(obj, dict):
            return {k: ("<redacted>" if k.lower() in _SECRET_KEYS else _redact_obj(v)) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return type(obj)(_redact_obj(v) for v in obj)
        return obj
    except Exception:
        return obj


def _build_json_record(record: Dict[str, Any]) -> Dict[str, Any]:
    # record structure provided by loguru
    extra = record.get("extra", {}) or {}
    # Resolve correlation from extra or contextvars
    trace_id = extra.get("trace_id") or trace_context.get_trace_id()
    request_id = extra.get("request_id") or trace_context.get_request_id()
    job_id = extra.get("job_id") or trace_context.get_job_id()

    data: Dict[str, Any] = {
        "ts": _to_iso8601(record["time"].datetime),
        "level": record["level"].name,
        "logger": extra.get("name") or record.get("name") or record.get("module"),
        "message": _redact_str(record.get("message", "")),
        "trace_id": trace_id,
        "job_id": job_id,
        "request_id": request_id,
        "module": record.get("module"),
    }

    # Exception details, if present
    exc = record.get("exception")
    if exc:
        try:
            # exc is a loguru Exception object with .format()
            formatted = "".join(exc.format())
        except Exception:
            formatted = str(exc)
        data["exception"] = _redact_str(formatted)

    # Include any user extras (redacted)
    user_extras = {k: v for k, v in extra.items() if k not in ("trace_id", "request_id", "job_id")}
    if user_extras:
        data["extra"] = _redact_obj(user_extras)

    return data


class LogManager:
    """
    Log manager

    Configures and manages logging
    """

    def __init__(self):
        """Initialize log manager"""
        # Remove default handlers
        logger.remove()

    def _bool_env(self, key: str, default: bool = False) -> bool:
        val = os.environ.get(key)
        if val is None:
            return default
        return str(val).lower() in {"1", "true", "yes", "y", "on"}

    def configure(self, config: Dict[str, Any]) -> None:
        """
        Configure logging

        Args:
            config (Dict[str, Any]): Logging configuration
        """
        level = config.get("level", "INFO")
        redact_sensitive = config.get("redact_sensitive", True)

        # Pretty console logs toggle (CLI/env can override)
        pretty_console = config.get("pretty_console")
        if pretty_console is None:
            pretty_console = self._bool_env("OPENCONTEXT_LOG_PRETTY", False) or self._bool_env(
                "LOG_PRETTY", False
            )

        def json_formatter(record: Dict[str, Any]) -> str:
            data = _build_json_record(record)
            if not redact_sensitive:
                # If explicitly disabled, try to recover original message/extras
                data["message"] = record.get("message", "")
                if "extra" in data:
                    data["extra"] = record.get("extra", {})
            return json.dumps(data, ensure_ascii=False)

        # Console logging
        if pretty_console:
            console_format = (
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{extra[name] if extra.get('name') else module}</cyan>: "
                "<white>{message}</white> "
                "<magenta>{extra[trace_id] if extra.get('trace_id') else ''}</magenta>"
            )
            logger.add(sys.stderr, level=level, format=console_format, backtrace=True, diagnose=False)
        else:
            logger.add(sys.stderr, level=level, format=json_formatter, backtrace=True, diagnose=False)

        # File logging (always JSON)
        log_path = config.get("log_path")
        if log_path:
            log_dir = os.path.dirname(log_path)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)

            # Add date to log filename: opencontext_2025-10-13.log
            base_name = os.path.basename(log_path)
            name_without_ext = os.path.splitext(base_name)[0]
            ext = os.path.splitext(base_name)[1]
            dated_log_path = os.path.join(log_dir, f"{name_without_ext}_{{time:YYYY-MM-DD}}{ext}")

            rotation = "100 MB"
            retention = 2  # Keep only the 2 most recent files

            logger.add(
                dated_log_path,
                level=level,
                format=json_formatter,
                rotation=rotation,
                retention=retention,
                encoding="utf-8",
                backtrace=True,
                diagnose=False,
            )

    def get_logger(self):
        """
        Get logger instance

        Returns:
            Logger: Logger instance
        """
        return logger


# Create global log manager instance
log_manager = LogManager()

# Export logger for use by other modules
log = logger
