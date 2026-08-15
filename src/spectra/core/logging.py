"""Structured logging with secret redaction."""

from __future__ import annotations

import logging
import re
from typing import Any, Mapping, MutableMapping

import structlog

_SENSITIVE = re.compile(
    r"(password|secret|token|api[_-]?key|authorization|credential)",
    re.IGNORECASE,
)


def _filter_sensitive(
    _: Any, __: str, event_dict: MutableMapping[str, Any]
) -> Mapping[str, Any]:
    for key in list(event_dict.keys()):
        if _SENSITIVE.search(str(key)):
            event_dict[key] = "***REDACTED***"
        elif isinstance(event_dict[key], str) and _SENSITIVE.search(event_dict[key]):
            event_dict[key] = "***REDACTED***"
    return event_dict


def configure_logging(level: str = "INFO", json_logs: bool = False) -> None:
    shared = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        _filter_sensitive,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if json_logs:
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()
    structlog.configure(
        processors=shared + [renderer],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO))


def get_logger(name: str | None = None) -> Any:
    return structlog.get_logger(name)
