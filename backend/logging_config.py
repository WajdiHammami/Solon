"""Process-wide logging setup.

Modules log through ``logging.getLogger(__name__)``; this only decides where
records go and at what level. Call :func:`configure_logging` once at startup.

Records go to the console and, when ``log_file`` is set, to a size-rotated
file (``solon.log``, ``solon.log.1``, ... up to ``backup_count`` old files).
Every line carries the request id (``[-]`` outside a request); see
:mod:`backend.request_context`.

Never log secrets, prompts, or article bodies — URLs, ids, counts, timings,
and token usage are enough to debug with.
"""

import logging.config
from pathlib import Path

# Third-party loggers that are noisy at INFO (one line per HTTP request).
_QUIET_LOGGERS = ("httpx", "httpcore", "openai", "groq")


def configure_logging(
    level: str = "INFO",
    log_file: Path | None = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> None:
    handlers: dict[str, dict] = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "filters": ["request_id"],
        },
    }
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "default",
            "filters": ["request_id"],
            "filename": str(log_file),
            "maxBytes": max_bytes,
            "backupCount": backup_count,
            "encoding": "utf-8",
        }

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "request_id": {"()": "backend.request_context.RequestIdFilter"},
            },
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)-8s [%(request_id)s] "
                    "%(name)s: %(message)s",
                },
            },
            "handlers": handlers,
            "loggers": {
                "backend": {"level": level.upper()},
                **{name: {"level": "WARNING"} for name in _QUIET_LOGGERS},
            },
            "root": {"level": "WARNING", "handlers": list(handlers)},
        }
    )
