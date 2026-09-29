# backend/tests/test_sse.py
"""SSE wire format."""

from app.events.sse import format_comment, format_sse


def test_message_is_a_data_line_and_a_blank_line() -> None:
    assert format_sse('{"a": 1}') == 'data: {"a": 1}\n\n'


def test_multiline_data_becomes_one_data_line_per_line() -> None:
    assert format_sse("one\ntwo") == "data: one\ndata: two\n\n"


def test_empty_data_is_still_a_message() -> None:
    assert format_sse("") == "data: \n\n"


def test_comment_starts_with_a_colon() -> None:
    assert format_comment("heartbeat") == ": heartbeat\n\n"
