

# SSE is a tiny text protocol, and getting it wrong fails silently in the browser. Keeping the formatting in two pure functions makes it trivial to test.

# backend/app/events/sse.py
"""Server-Sent Events wire format (https://html.spec.whatwg.org/#server-sent-events)."""


def format_sse(data: str) -> str:
    """One SSE message. A newline inside `data` would end the field early, so split on it."""
    lines = data.splitlines() or [""]
    return "".join(f"data: {line}\n" for line in lines) + "\n"


def format_comment(text: str) -> str:
    """A comment line. Browsers ignore it; it keeps the connection alive through proxies."""
    return f": {text}\n\n"
