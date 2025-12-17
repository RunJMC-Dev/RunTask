from __future__ import annotations
import json
from datetime import datetime
from typing import Any

from .const import K_NAME, K_LIST, K_START_DATE, K_PERIOD_DAYS


def parse_tasks_blob(blob: str) -> list[dict[str, Any]]:
    """Parse tasks from a JSON blob provided via the UI."""
    try:
        parsed = json.loads(blob or "[]")
    except Exception as e:
        raise ValueError(f"Tasks must be valid JSON: {e}") from e
    if not isinstance(parsed, list):
        raise ValueError("Tasks must be a JSON list")
    return validate_tasks(parsed)


def validate_tasks(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for i, t in enumerate(raw or []):
        try:
            name = t[K_NAME]
            list_entity = t[K_LIST]
            start_date = t[K_START_DATE]
            _ = datetime.strptime(start_date, "%Y-%m-%d")  # validate format
            pd = int(t[K_PERIOD_DAYS])
            if pd <= 0:
                raise ValueError("period_days must be > 0")
            out.append(
                {
                    K_NAME: name,
                    K_LIST: list_entity,
                    K_START_DATE: start_date,
                    K_PERIOD_DAYS: pd,
                }
            )
        except Exception as e:
            raise ValueError(f"Invalid task at index {i}: {e}") from e
    return out
