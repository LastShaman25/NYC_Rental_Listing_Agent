"""Structured JSON logging (PR-NFR-005).

Log events are JSON lines written to stderr and optionally to
``local_data/logs/``. Credentials, session tokens, signed URLs, and contact data
must never be logged; loggers receive only IDs, statuses, and sanitized context.
"""

import logging
import sys
from pathlib import Path

import structlog


def configure_logging(log_dir: Path | None = None, level: int = logging.INFO) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_dir / "rental_agent.jsonl", encoding="utf-8"))

    logging.basicConfig(level=level, format="%(message)s", handlers=handlers, force=True)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
