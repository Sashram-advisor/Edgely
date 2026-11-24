"""T3: the stream's error event must never leak exception text (app/core/tutor_sse.py)."""

from __future__ import annotations

import json

from app.core.tutor_sse import (
    TutorStreamErrorCode,
    classify_exception,
    error_event_for,
    format_event,
)

SECRET = "postgresql://postgres:hunter2@db.internal:5432/postgres sk-ant-api03-SECRET"


def _fake_exception(module: str, name: str, status_code: int | None = None) -> Exception:
    """Build an exception that looks like it came from another library.

    The classifier matches by module and class name, so we can test it without
    installing anthropic or postgrest.
    """
    cls = type(name, (Exception,), {"__module__": module})
    exc = cls(SECRET)
    if status_code is not None:
        exc.status_code = status_code  # type: ignore[attr-defined]
    return exc


def _parse(frame: str) -> tuple[str, dict]:
    """Split one SSE frame into (event name, JSON data)."""
    lines = frame.strip("\n").split("\n")
    assert lines[0].startswith("event: ")
    assert lines[1].startswith("data: ")
    assert len(lines) == 2, "payload must fit on one data: line"
    return lines[0][len("event: "):], json.loads(lines[1][len("data: "):])


def test_frame_format_is_one_event_line_one_data_line() -> None:
    frame = format_event("delta", {"text": "line one\nline two"})
    assert frame.endswith("\n\n")
    event, data = _parse(frame)
    assert event == "delta"
    assert data == {"text": "line one\nline two"}


def test_error_event_never_contains_the_exception_text(caplog) -> None:
    frame = error_event_for(RuntimeError(SECRET), user_id=7, conversation_id=42)
    event, data = _parse(frame)

    assert event == "error"
    assert "hunter2" not in frame and "SECRET" not in frame
    assert data["code"] == "TUTOR_INTERNAL_ERROR"
    assert data["retryable"] is False
    assert data["detail"] == data["message"]  # deprecated alias, same safe text
    assert len(data["error_id"]) == 32

    # The full detail is still available to operators, tied to the same error_id.
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert data["error_id"] in logged
    assert "user_id=7" in logged and "conversation_id=42" in logged


def test_each_error_gets_its_own_id() -> None:
    first = _parse(error_event_for(RuntimeError("a")))[1]["error_id"]
    second = _parse(error_event_for(RuntimeError("a")))[1]["error_id"]
    assert first != second


def test_provider_failures_are_classified() -> None:
    cases = {
        ("anthropic._exceptions", "RateLimitError", 429): TutorStreamErrorCode.MODEL_RATE_LIMITED,
        ("anthropic._exceptions", "InternalServerError", 500): TutorStreamErrorCode.MODEL_UNAVAILABLE,
        ("anthropic._exceptions", "APIStatusError", 529): TutorStreamErrorCode.MODEL_UNAVAILABLE,
        ("anthropic._exceptions", "APIConnectionError", None): TutorStreamErrorCode.MODEL_UNAVAILABLE,
        ("anthropic._exceptions", "APITimeoutError", None): TutorStreamErrorCode.MODEL_UNAVAILABLE,
        # A bad API key is our configuration problem, not a provider outage.
        ("anthropic._exceptions", "AuthenticationError", 401): TutorStreamErrorCode.INTERNAL_ERROR,
        ("postgrest.exceptions", "APIError", None): TutorStreamErrorCode.SAVE_FAILED,
        ("builtins", "KeyError", None): TutorStreamErrorCode.INTERNAL_ERROR,
    }
    for (module, name, status), expected in cases.items():
        assert classify_exception(_fake_exception(module, name, status)) is expected, name


def test_every_code_has_a_message_and_none_leak() -> None:
    for module, name, status in [
        ("anthropic._exceptions", "RateLimitError", 429),
        ("anthropic._exceptions", "InternalServerError", 503),
        ("postgrest.exceptions", "APIError", None),
        ("builtins", "ValueError", None),
    ]:
        frame = error_event_for(_fake_exception(module, name, status))
        _, data = _parse(frame)
        assert data["message"]
        assert "hunter2" not in frame
