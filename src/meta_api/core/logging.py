from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
_SENSITIVE = ("token", "secret", "password", "authorization", "cookie", "payload")


class StructuredFormatter(logging.Formatter):
    """Format records as one machine-readable JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None) or request_id_context.get()
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for key in list(record.__dict__):
            if any(secret in key.lower() for secret in _SENSITIVE):
                delattr(record, key)
        return True


def configure_logging(level: str) -> None:
    """Configure the root logger without duplicating handlers on reload."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    handler.addFilter(RequestContextFilter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
