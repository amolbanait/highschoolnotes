"""Logging with a filter that redacts secrets before anything is written."""

import logging
import re

_PATTERNS = [
    # key=value and "key": "value" forms for sensitive keys
    re.compile(
        r"(?i)(\"?(?:password|passwd|secret|token|api[_-]?key|authorization|cookie|session)\"?\s*[:=]\s*)"
        r"(\"[^\"]*\"|'[^']*'|[^\s,;}]+)"
    ),
    re.compile(r"sk-ant-[A-Za-z0-9_\-]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
]


def redact(text: str) -> str:
    text = _PATTERNS[2].sub("Bearer [REDACTED]", text)
    text = _PATTERNS[1].sub("[REDACTED]", text)
    return _PATTERNS[0].sub(lambda m: m.group(1) + "[REDACTED]", text)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = redact(message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(RedactingFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
