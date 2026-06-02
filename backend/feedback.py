"""Minimal feedback sink (Module E, 主计划 §3.4 / R1.3).

Appends one JSON line per feedback event to data_processed/feedback.jsonl.
No model update — just durable capture of "which candidate did the user pick,
and how did they rate it" for later analysis.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402

FEEDBACK_LOG = C.DATA_PROCESSED / "feedback.jsonl"


def record(entry: dict) -> int:
    """Append a feedback entry; return the total number of records."""
    with open(FEEDBACK_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return count()


def count() -> int:
    if not FEEDBACK_LOG.exists():
        return 0
    with open(FEEDBACK_LOG, encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())
