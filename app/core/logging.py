"""Structured logging configuration using structlog.

Pretty console output locally; machine-readable JSON everywhere else (for log
aggregation). A request id is bound per request by the middleware.

Both structlog events and stdlib records (uvicorn, sqlalchemy, alembic) are
routed through the same renderer via ``ProcessorFormatter``, so production
emits one consistent format with correlation ids instead of a mix of shapes.
Uvicorn's own access log is disabled — the context middleware emits a richer
structured access event per request.
"""

import logging
import sys

import structlog

from app.core.config import Environment, Settings


def configure_logging(settings: Settings) -> None:
    log_level = logging.DEBUG if settings.app.debug else logging.INFO

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    tail_processors: list[structlog.types.Processor]
    if settings.environment is Environment.LOCAL:
        # ConsoleRenderer pretty-prints exc_info itself.
        tail_processors = [structlog.dev.ConsoleRenderer()]
    else:
        tail_processors = [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        # Applied to records that did not originate from structlog.
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            *tail_processors,
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(log_level)

    # Route uvicorn through the root handler; drop its plain-text access log —
    # RequestContextMiddleware emits a structured access event instead.
    for name in ("uvicorn", "uvicorn.error"):
        stdlib_logger = logging.getLogger(name)
        stdlib_logger.handlers = []
        stdlib_logger.propagate = True
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers = []
    access_logger.propagate = False
