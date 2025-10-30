#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
Configuration Validator

Validates configuration against schema and provides clear error messages
with actionable fixes for users.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from opencontext.utils.logging_utils import get_logger

logger = get_logger(__name__)


class ConfigValidationError:
    """Represents a configuration validation error with context and fix suggestions"""

    def __init__(self, field: str, message: str, fix_suggestion: str = "", severity: str = "error"):
        self.field = field
        self.message = message
        self.fix_suggestion = fix_suggestion
        self.severity = severity  # "error", "warning", "info"

    def __str__(self):
        result = f"[{self.severity.upper()}] {self.field}: {self.message}"
        if self.fix_suggestion:
            result += f"\n  💡 Fix: {self.fix_suggestion}"
        return result


class ConfigValidator:
    """Validates configuration and provides helpful error messages"""

    # CRITICAL parameters that must be set
    REQUIRED_FIELDS = {
        "vlm_model": ["model", "base_url"],
        "embedding_model": ["model", "base_url", "dimensions"],
    }

    # Parameters that are provider-specific
    PROVIDER_API_KEY_REQUIRED = ["openai", "doubao"]
    PROVIDER_API_KEY_OPTIONAL = ["ollama", "localai", "llamacpp", "custom"]

    # Embedding model dimension registry (model -> dimensions)
    EMBEDDING_DIMENSIONS = {
        # Ollama
        "nomic-embed-text": 768,
        "mxbai-embed-large": 1024,
        "bge-m3": 1024,
        "all-minilm": 384,
        "nomic-embed-text-v1.5": 768,
        # OpenAI
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        # Doubao
        "doubao-embedding": 1024,
    }

    def __init__(self):
        self.errors: List[ConfigValidationError] = []
        self.warnings: List[ConfigValidationError] = []

    def validate(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate configuration

        Args:
            config: Configuration dictionary to validate

        Returns:
            (is_valid, error_messages)
        """
        self.errors = []
        self.warnings = []

        # Validate required fields
        self._validate_required_fields(config)

        # Validate LLM configuration
        self._validate_vlm_config(config.get("vlm_model", {}))

        # Validate embedding configuration
        self._validate_embedding_config(config.get("embedding_model", {}))

        # Validate web configuration
        self._validate_web_config(config.get("web", {}))

        # Generate error messages
        error_messages = [str(error) for error in self.errors]
        warning_messages = [str(warning) for warning in self.warnings]

        if error_messages:
            logger.error(f"Configuration validation failed with {len(error_messages)} error(s)")

        if warning_messages:
            logger.warning(f"Configuration has {len(warning_messages)} warning(s)")

        return len(self.errors) == 0, error_messages + warning_messages

    def _validate_required_fields(self, config: Dict[str, Any]):
        """Validate that all required fields exist"""
        for section, fields in self.REQUIRED_FIELDS.items():
            if section not in config:
                self.errors.append(
                    ConfigValidationError(
                        section,
                        f"Missing required section: {section}",
                        f"Add '{section}' section to your config/user/config.yaml",
                        "error",
                    )
                )
                continue

            section_config = config[section]
            for field in fields:
                if field not in section_config or not section_config[field]:
                    self.errors.append(
                        ConfigValidationError(
                            f"{section}.{field}",
                            f"Missing or empty required field",
                            f"Add '{field}' to {section} in config/user/config.yaml or set via .env",
                            "error",
                        )
                    )

    def _validate_vlm_config(self, vlm_config: Dict[str, Any]):
        """Validate Vision Language Model configuration"""
        if not vlm_config:
            return

        provider = vlm_config.get("provider", "").lower()
        api_key = vlm_config.get("api_key", "")

        # Validate provider
        valid_providers = ["openai", "doubao", "ollama", "localai", "llamacpp", "custom"]
        if provider and provider not in valid_providers:
            self.warnings.append(
                ConfigValidationError(
                    "vlm_model.provider",
                    f"Unknown provider: {provider}",
                    f"Use one of: {', '.join(valid_providers)}",
                    "warning",
                )
            )

        # Validate API key requirement
        if provider in self.PROVIDER_API_KEY_REQUIRED:
            if not api_key:
                fix = f"Set LLM_API_KEY environment variable and use ${{LLM_API_KEY}} in config"
                self.errors.append(
                    ConfigValidationError(
                        "vlm_model.api_key",
                        f"API key required for {provider} but not set",
                        fix,
                        "error",
                    )
                )

    def _validate_embedding_config(self, embedding_config: Dict[str, Any]):
        """Validate embedding model configuration"""
        if not embedding_config:
            return

        provider = embedding_config.get("provider", "").lower()
        model = embedding_config.get("model", "")
        dimensions = embedding_config.get("dimensions")
        api_key = embedding_config.get("api_key", "")

        # CRITICAL: Validate dimensions
        if dimensions is None:
            self.errors.append(
                ConfigValidationError(
                    "embedding_model.dimensions",
                    "CRITICAL: dimensions parameter is missing!",
                    "Set 'dimensions' in embedding_model to match your model:\n"
                    "  - Ollama nomic-embed-text: 768\n"
                    "  - Ollama mxbai-embed-large: 1024\n"
                    "  - OpenAI text-embedding-3-small: 1536\n"
                    "  - OpenAI text-embedding-3-large: 3072\n"
                    "  - Doubao: 1024",
                    "error",
                )
            )
        elif not isinstance(dimensions, int) or dimensions <= 0:
            self.errors.append(
                ConfigValidationError(
                    "embedding_model.dimensions",
                    f"Invalid dimensions value: {dimensions}",
                    "dimensions must be a positive integer matching your embedding model",
                    "error",
                )
            )

        # Validate dimensions match known models (warning only)
        if model and model in self.EMBEDDING_DIMENSIONS:
            expected_dims = self.EMBEDDING_DIMENSIONS[model]
            if dimensions and dimensions != expected_dims:
                self.warnings.append(
                    ConfigValidationError(
                        "embedding_model.dimensions",
                        f"dimensions={dimensions} may not match model {model}",
                        f"Expected dimensions={expected_dims} for model '{model}'",
                        "warning",
                    )
                )

        # Validate provider
        valid_providers = ["openai", "doubao", "ollama", "localai", "llamacpp", "custom"]
        if provider and provider not in valid_providers:
            self.warnings.append(
                ConfigValidationError(
                    "embedding_model.provider",
                    f"Unknown provider: {provider}",
                    f"Use one of: {', '.join(valid_providers)}",
                    "warning",
                )
            )

        # Validate API key requirement
        if provider in self.PROVIDER_API_KEY_REQUIRED:
            if not api_key:
                fix = f"Set EMBEDDING_API_KEY or LLM_API_KEY environment variable"
                self.errors.append(
                    ConfigValidationError(
                        "embedding_model.api_key",
                        f"API key required for {provider} but not set",
                        fix,
                        "error",
                    )
                )

    def _validate_web_config(self, web_config: Dict[str, Any]):
        """Validate web server configuration"""
        if not web_config:
            return

        # Validate port
        port = web_config.get("port")
        if port is not None:
            if not isinstance(port, int) or not (1 <= port <= 65535):
                self.errors.append(
                    ConfigValidationError(
                        "web.port",
                        f"Invalid port: {port}",
                        "port must be an integer between 1 and 65535",
                        "error",
                    )
                )

        # Validate host
        host = web_config.get("host", "")
        if host:
            # Simple validation - just check it's not empty
            if not isinstance(host, str):
                self.errors.append(
                    ConfigValidationError(
                        "web.host",
                        f"Invalid host: {host}",
                        "host must be a string like '127.0.0.1' or '0.0.0.0'",
                        "error",
                    )
                )

    def get_error_summary(self) -> str:
        """Get a summary of all errors and warnings"""
        if not self.errors and not self.warnings:
            return "✅ Configuration is valid!"

        summary = []
        if self.errors:
            summary.append(f"❌ {len(self.errors)} Error(s):")
            for error in self.errors:
                summary.append(f"  {error}")

        if self.warnings:
            summary.append(f"⚠️  {len(self.warnings)} Warning(s):")
            for warning in self.warnings:
                summary.append(f"  {warning}")

        return "\n".join(summary)

    @staticmethod
    def get_embedding_dimensions_ref() -> str:
        """Get a reference of common embedding dimensions"""
        ref = "Common embedding model dimensions:\n"
        ref += "\nOllama:\n"
        for model, dims in ConfigValidator.EMBEDDING_DIMENSIONS.items():
            if model.startswith("nomic") or model.startswith("mxbai") or model.startswith("bge") or model.startswith("all"):
                ref += f"  {model}: {dims}\n"
        ref += "\nOpenAI:\n"
        for model, dims in ConfigValidator.EMBEDDING_DIMENSIONS.items():
            if model.startswith("text-embedding"):
                ref += f"  {model}: {dims}\n"
        ref += "\nDoubao:\n"
        for model, dims in ConfigValidator.EMBEDDING_DIMENSIONS.items():
            if model.startswith("doubao"):
                ref += f"  {model}: {dims}\n"
        return ref
