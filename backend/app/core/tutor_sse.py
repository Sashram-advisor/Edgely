"""Server-Sent Events helpers for ``POST /tutor/chat/stream`` (T3).

The full wire contract is documented in ``docs/api/tutor-sse.md``. This module
is the single place that:

* formats one SSE frame (``format_event``), and
* turns an exception raised *after* the stream started into a safe, stable
  ``error`` event (``error_event_for``).

Why sanitise?
-------------
Before T3 the route did ``yield _sse("error", {"detail": str(exc)})``. Exception
text from inside the service can contain SQL, table names, Supabase URLs, model
names or even fragments of API keys, and it went straight to the browser. Now
the browser only ever receives one of the fixed codes below plus a fixed,
human-readable message. The real exception is written to the server log
together with an ``error_id`` that is also sent to the client, so a support
request ("I got error 3f2a…") can be matched to the log line.

Nothing in this module imports ``anthropic`` or ``postgrest`` directly: the
platform API must still import even when the tutor's optional dependencies are
missing. Exceptions are classified by class name and module instead.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any

log = logging.getLogger("edgely.tutor.stream")

# Event names, kept as constants so the route, the tests and the docs agree.
EVENT_META = "meta"
EVENT_DELTA = "delta"
EVENT_DONE = "done"
EVENT_ERROR = "error"


class TutorStreamErrorCode(str, Enum):
    """Stable error codes sent in the ``error`` event.

    Clients switch on these values, so they are part of the public contract:
    never rename one. Add new codes at the end and document them in
    ``docs/api/tutor-sse.md``.
    """

    #: The language-model provider is down, overloaded or timed out. Retrying later may work.
    MODEL_UNAVAILABLE = "TUTOR_MODEL_UNAVAILABLE"
    #: The language-model provider rate-limited *us* (not the learner). Retrying later may work.
    MODEL_RATE_LIMITED = "TUTOR_MODEL_RATE_LIMITED"
    #: The answer was generated but could not be saved to the database.
    SAVE_FAILED = "TUTOR_SAVE_FAILED"
    #: Anything else. A bug: look up ``error_id`` in the server log.
    INTERNAL_ERROR = "TUTOR_INTERNAL_ERROR"


# Fixed, user-safe text for each code. Never interpolate exception text here.
_MESSAGES: dict[TutorStreamErrorCode, str] = {
    TutorStreamErrorCode.MODEL_UNAVAILABLE: "The tutor is temporarily unavailable. Please try again in a minute.",
    TutorStreamErrorCode.MODEL_RATE_LIMITED: "The tutor is very busy right now. Please try again in a minute.",
    TutorStreamErrorCode.SAVE_FAILED: "Your answer could not be saved. Please ask again.",
    TutorStreamErrorCode.INTERNAL_ERROR: "Something went wrong while answering. Please try again.",
}

# Whether a retry of the same question has a reasonable chance of succeeding.
_RETRYABLE: dict[TutorStreamErrorCode, bool] = {
    TutorStreamErrorCode.MODEL_UNAVAILABLE: True,
    TutorStreamErrorCode.MODEL_RATE_LIMITED: True,
    TutorStreamErrorCode.SAVE_FAILED: True,
    TutorStreamErrorCode.INTERNAL_ERROR: False,
}

# anthropic SDK exception class names, grouped by the code they map to.
# (Matching by name keeps this module importable without the anthropic package.)
_MODEL_RATE_LIMIT_NAMES = {"RateLimitError"}
_MODEL_UNAVAILABLE_NAMES = {
    "APIConnectionError",
    "APITimeoutError",
    "InternalServerError",
    "OverloadedError",
    "ServiceUnavailableError",
}


@dataclass(frozen=True)
class StreamError:
    """What the client is allowed to see about a failure."""

    code: TutorStreamErrorCode
    message: str
    retryable: bool
    error_id: str

    def as_payload(self) -> dict[str, Any]:
        """JSON body of the ``error`` event.

        ``detail`` duplicates ``message`` only for clients written before T3,
        which read ``detail``. It is deprecated; new code reads ``code`` and
        ``message``.
        """
        return {
            "code": self.code.value,
            "message": self.message,
            "retryable": self.retryable,
            "error_id": self.error_id,
            "detail": self.message,
        }


def format_event(event: str, data: dict[str, Any]) -> str:
    """Return one SSE frame: ``event:`` line, one ``data:`` line, blank line.

    ``json.dumps`` never emits a raw newline (newlines inside strings become
    ``\\n``), so the payload always fits on a single ``data:`` line.
    """
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def classify_exception(exc: BaseException) -> TutorStreamErrorCode:
    """Map an exception to a stable code without looking at its message text."""
    # Walk the MRO so subclasses (e.g. a future anthropic.OverloadedError
    # subclass) are still recognised.
    names = {cls.__name__ for cls in type(exc).__mro__}
    module = type(exc).__module__ or ""

    if module.startswith("anthropic"):
        status = getattr(exc, "status_code", None)
        if names & _MODEL_RATE_LIMIT_NAMES or status == 429:
            return TutorStreamErrorCode.MODEL_RATE_LIMITED
        # Network problems, timeouts, 5xx and "overloaded" (529) are the
        # provider's side: a retry later may work.
        if names & _MODEL_UNAVAILABLE_NAMES or (isinstance(status, int) and status >= 500):
            return TutorStreamErrorCode.MODEL_UNAVAILABLE
        # Other 4xx (bad API key, request too large, ...) are our own
        # configuration or code problem: fall through to INTERNAL_ERROR.
        return TutorStreamErrorCode.INTERNAL_ERROR
    if module.startswith(("postgrest", "supabase", "httpx")):
        # The model call finished; the failure happened while persisting via PostgREST.
        return TutorStreamErrorCode.SAVE_FAILED
    return TutorStreamErrorCode.INTERNAL_ERROR


def error_event_for(exc: BaseException, *, user_id: int | None = None, conversation_id: int | None = None) -> str:
    """Log ``exc`` with full detail server-side and return a sanitised SSE ``error`` frame.

    The log line carries ``error_id``, ``user_id`` and ``conversation_id`` so an
    operator can find it; the client only gets the code, a fixed message and
    the same ``error_id``.
    """
    code = classify_exception(exc)
    error = StreamError(
        code=code,
        message=_MESSAGES[code],
        retryable=_RETRYABLE[code],
        error_id=uuid.uuid4().hex,
    )
    # log.exception records the traceback; it is only ever written to the server log.
    log.exception(
        "tutor stream failed error_id=%s code=%s user_id=%s conversation_id=%s",
        error.error_id,
        code.value,
        user_id,
        conversation_id,
        exc_info=exc,
    )
    return format_event(EVENT_ERROR, error.as_payload())
