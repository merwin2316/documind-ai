"""
Pipeline tracer — safe diagnostic logging for every step in the RAG pipeline.
Prints non-sensitive execution metadata (durations, counts, statuses) to stdout.
"""
import time
import re
from typing import Any

_INDENT = 0

# Patterns for keys that could hold sensitive content or PII
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(question|message|prompt|response|context|preview|query|user_id|email|password|secret|token|api_key|raw_)",
    re.IGNORECASE,
)


def _sanitize_val(key: str, val: Any) -> str:
    """Ensure sensitive data is not leaked in trace output."""
    if _SENSITIVE_KEY_PATTERN.search(key):
        if isinstance(val, str):
            return f"<redacted: len={len(val)}>"
        elif isinstance(val, (list, tuple, dict, set)):
            return f"<redacted: count={len(val)}>"
        return "<redacted>"

    val_str = repr(val)
    if len(val_str) > 120:
        val_str = val_str[:120] + "... (truncated)"
    return val_str


def trace(label: str, **kwargs):
    """Print a labelled trace line with sanitized diagnostic metadata."""
    pad = "  " * _INDENT
    print(f"\n{pad}[TRACE] {label}", flush=True)
    if kwargs:
        for k, v in kwargs.items():
            safe_str = _sanitize_val(k, v)
            print(f"{pad}        {k} = {safe_str}", flush=True)


class _Step:
    def __init__(self, name: str, **kwargs):
        self.name = name
        self.kwargs = kwargs
        self.t0 = None

    def __enter__(self):
        global _INDENT
        trace(f"ENTER {self.name}", **self.kwargs)
        self.t0 = time.perf_counter()
        _INDENT += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        global _INDENT
        _INDENT = max(0, _INDENT - 1)
        elapsed = time.perf_counter() - self.t0
        if exc_type:
            trace(f"ERROR {self.name}", elapsed_s=round(elapsed, 2), error_type=type(exc_val).__name__)
        else:
            trace(f"EXIT  {self.name}", elapsed_s=round(elapsed, 2))
        return False  # never suppress exceptions


def step(name: str, **kwargs) -> _Step:
    return _Step(name, **kwargs)
