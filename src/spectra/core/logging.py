"""Structured logging configuration. Secrets are never logged."""

from __future__ import annotations

import logging
import sys
from collections.abc import Mapping, MutableMapping
from typing import Any

import structlog

_SENSITIVE_KEYS = frozenset({
    "api_key", "apikey", "token", "password", "secret", "authorization",
    "model_api_key", "auth_evidence", "raw_excerpt",
})


def _filter_sensitive(_: Any, __: str, event_dict: MutableMapping[str, Any]) -> Mapping[str, Any]:
    for key in list(event_dict.keys()):
        lower = key.lower()
        if lower in _SENSITIVE_KEYS or any(s in lower for s in ("password", "secret", "token", "key")):
            event_dict[key] = "[REDACTED]"
    return event_dict


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=getattr(logging, level.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _filter_sensitive,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "spectra") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
