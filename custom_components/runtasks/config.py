from __future__ import annotations
from datetime import datetime
from typing import Any

from .const import K_NAME, K_LIST, K_START_DATE, K_PERIOD_DAYS, K_WEEKDAY


def validate_tasks(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for i, t in enumerate(raw or []):
        try:
            _ = t[K_NAME]
            _ = t[K_LIST]
            sd = datetime.strptime(t[K_START_DATE], "%Y-%m-%d")  # validate
            pd = int(t[K_PERIOD_DAYS])
            wd = int(t[K_WEEKDAY])
            if not (0 <= wd <= 6):
                raise ValueError("weekday must be 0..6")
            if pd <= 0:
                raise ValueError("period_days must be > 0")
            out.append(t)
        except Exception as e:
            raise ValueError(f"Invalid task at index {i}: {e}") from e
    return out
