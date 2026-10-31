"""Per-request id used to correlate log lines.

The id lives in a :class:`~contextvars.ContextVar`, so it follows the request
into async tasks and worker threads (both copy the context), and
:class:`RequestIdFilter` stamps it on every log record. Outside a request it
is ``"-"``.
"""

import logging
import re
import uuid
from contextvars import ContextVar, Token

REQUEST_ID_HEADER = "X-Request-ID"

_request_id: ContextVar[str] = ContextVar("request_id", default="-")

# Ids from callers end up in log lines; only accept short, inert ones so a
# client can't inject fake log entries (newlines, control characters, ...).
_SAFE_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")


def resolve_request_id(incoming: str | None) -> str:
    """Reuse the caller's id when it is safe to log, otherwise make one."""
    if incoming and _SAFE_ID.fullmatch(incoming):
        return incoming
    return uuid.uuid4().hex[:12]


def get_request_id() -> str:
    return _request_id.get()


def set_request_id(request_id: str) -> Token:
    return _request_id.set(request_id)


def reset_request_id(token: Token) -> None:
    _request_id.reset(token)


class RequestIdFilter(logging.Filter):
    """Adds ``record.request_id`` for the ``%(request_id)s`` format field."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True
