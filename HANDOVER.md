RunTasks — Handover for Codex
0) Mission & Scope

Goal: A Home Assistant custom integration that adds items to existing to-do list entities on a recurring schedule (e.g. “Red Bin every 2nd Tuesday”, “Vacuuming every Saturday”), with items appearing at local midnight on their due day.

Out of scope (v0.1):

UI config-flow (YAML only in v0.1; add config-flow later).

Editing/marking to-dos beyond using core todo.* actions.

Complex calendars/holidays (possible future add-on).

1) Domain, Naming, Versioning

Display name: RunTasks

Python/HA domain (lowercase, no spaces): runtasks

Initial version: v0.1.0

Semantic versioning for releases.

2) Repo Layout (target)
RunTasks/
+- custom_components/
¦  +- runtasks/
¦     +- __init__.py
¦     +- manifest.json
¦     +- const.py
¦     +- scheduler.py
¦     +- coordinator.py           # (optional for future entities)
¦     +- config.py                # YAML parsing / validation helpers
¦     +- strings.json             # (optional now; for UI later)
¦     +- translations/            # (optional; for config_flow later)
+- hacs.json
+- README.md
+- CHANGELOG.md
+- LICENSE
+- HANDOVER.md                    # this file


HACS: single repo, integration content under custom_components/runtasks/.

3) Minimal Files (v0.1.0)
custom_components/runtasks/manifest.json
{
  "domain": "runtasks",
  "name": "RunTasks",
  "version": "0.1.0",
  "documentation": "",
  "requirements": [],
  "codeowners": ["@JonCorf"],
  "iot_class": "local_push"
}


Note: leave documentation empty for now (no placeholder links). Add when repo is public.

custom_components/runtasks/const.py
DOMAIN = "runtasks"
CONF_TASKS = "tasks"

# Task keys
K_NAME = "name"
K_LIST = "list"
K_START_DATE = "start_date"     # "YYYY-MM-DD" (local date)
K_PERIOD_DAYS = "period_days"   # int
K_WEEKDAY = "weekday"           # 0=Mon..6=Sun

MIDNIGHT_FMT = "%Y-%m-%d %H:%M:%S"  # due_datetime format

custom_components/runtasks/config.py
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

custom_components/runtasks/scheduler.py
from __future__ import annotations
from datetime import datetime, date, time, timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

from .const import MIDNIGHT_FMT, K_NAME, K_LIST, K_START_DATE, K_PERIOD_DAYS, K_WEEKDAY

async def schedule_midnight_daily(hass: HomeAssistant, tasks: list[dict]):
    async def _run(_now_utc):
        await process_due_tasks(hass, tasks)
        # schedule next local midnight
        next_local_midnight = dt_util.start_of_local_day(dt_util.now() + timedelta(days=1))
        next_utc = dt_util.as_utc(next_local_midnight)
        async_track_point_in_utc_time(hass, _run, next_utc)

    # first run: tonight local midnight (or run immediately if past)
    first = dt_util.start_of_local_day(dt_util.now())
    if dt_util.now() >= first + timedelta(minutes=1):
        # already past midnight; run once now then schedule tomorrow
        await process_due_tasks(hass, tasks)
        first = dt_util.start_of_local_day(dt_util.now() + timedelta(days=1))
    first_utc = dt_util.as_utc(first)
    async_track_point_in_utc_time(hass, _run, first_utc)

async def process_due_tasks(hass: HomeAssistant, tasks: list[dict]):
    tz_now = dt_util.now()                      # aware dt in HA local tz
    today: date = tz_now.date()
    for t in tasks:
        name = t[K_NAME]
        list_entity = t[K_LIST]
        start = datetime.strptime(t[K_START_DATE], "%Y-%m-%d").date()
        period = int(t[K_PERIOD_DAYS])
        weekday = int(t[K_WEEKDAY])

        if today.weekday() != weekday:
            continue
        days_since = (today - start).days
        if days_since < 0 or days_since % period != 0:
            continue

        # fetch current "needs_action" items
        resp = await hass.services.async_call(
            "todo", "get_items",
            {"entity_id": list_entity, "data": {"status": ["needs_action"]}},
            blocking=True, return_response=True
        )
        items = resp.get(list_entity, {}).get("items", [])
        if any(i.get("summary") == name for i in items):
            continue

        due = datetime.combine(today, time.min).strftime(MIDNIGHT_FMT)
        await hass.services.async_call(
            "todo", "add_item",
            {"entity_id": list_entity, "data": {"item": name, "due_datetime": due}},
            blocking=True
        )

custom_components/runtasks/__init__.py
from __future__ import annotations
from datetime import timedelta
import logging

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, CONF_TASKS
from .config import validate_tasks
from .scheduler import schedule_midnight_daily

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    # YAML-only v0.1: configuration.yaml -> runtasks: { tasks: [...] }
    domain_cfg = (config or {}).get(DOMAIN, {})
    tasks = validate_tasks(domain_cfg.get(CONF_TASKS, []))

    async def _on_started(_):
        await schedule_midnight_daily(hass, tasks)

    # Defer scheduling until HA is fully started
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_started)
    _LOGGER.info("RunTasks loaded with %d task(s)", len(tasks))
    return True

hacs.json
{
  "name": "RunTasks",
  "content_in_root": false,
  "render_readme": true,
  "domains": ["integration"],
  "homeassistant": "2024.12.0"
}

4) Configuration (YAML for v0.1)

Add to configuration.yaml:

runtasks:
  tasks:
    - name: "Red bin"
      list: "todo.house_chores"
      start_date: "2025-11-18"
      period_days: 14
      weekday: 1     # 0=Mon..6=Sun
    - name: "Yellow bin"
      list: "todo.house_chores"
      start_date: "2025-11-25"
      period_days: 14
      weekday: 1
    - name: "Vacuuming"
      list: "todo.house_chores"
      start_date: "2025-11-15"
      period_days: 7
      weekday: 5


Notes

start_date establishes the cadence anchor (e.g., alternate Tuesdays).

Items are injected with due_datetime at 00:00 local time on due days.

Duplicate prevention: we only add the item if there’s no existing needs_action item with the same summary in that list.

5) Dev Workflow (VS Code + HA)

Clone repo into your HA /config (or mount).

Ensure path is custom_components/runtasks/….

Settings ? Devices & Services ? Check Config then Restart.

Verify logs: “RunTasks loaded with %d task(s)”.

Create/identify a to-do list entity (e.g. Local To-do ? todo.house_chores).

(Dev) Temporarily change weekday/start_date to force a due condition and confirm item injection by manually running process_due_tasks (optional) or advancing system date/time in a test env.

6) Acceptance Criteria (v0.1)

? On the first HA start after install, RunTasks schedules itself to run at local midnight and re-schedules daily thereafter.

? On a due day, an item with the configured name is added to the target todo entity at 00:00 local time with due_datetime set to midnight.

? Duplicate items are not created if a needs_action item with the same summary already exists.

? Supports at least 40 tasks without separate automations.

7) Test Plan (manual)

Unit cadence: Use two bin tasks with 14-day periods and staggered start_dates a week apart; verify they alternate Tuesdays.

Weekly task: Vacuuming with period_days: 7 on weekday: 5; verify every Saturday.

Duplicate prevention: Pre-create Red bin in the list and run midnight job; ensure no second item is added.

Time zone: Confirm midnight is taken from HA local timezone (Sydney), not UTC.

8) Roadmap

v0.1.0 (current): YAML config, midnight scheduler, duplicate prevention, HACS-installable.

v0.2.0: Config Flow + Options Flow (UI add/edit tasks), per-task “inject time” override, optional pre-notice (e.g., T-1 day).

v0.3.0: Entity exposure (e.g., sensors with next due date per task), pause/resume toggles, holiday offsets (optional).

v0.4.0: Import/export tasks, migration helpers, tests.

9) Coding Guidelines

Async-first; use hass.services.async_call(..., blocking=True) only where needed.

Strict validation of YAML (see config.py).

No placeholder links in docs.

Keep logs informative but sparse (one info on load, warning on invalid config).

10) HACS Release Steps

Commit + tag: v0.1.0.

Add repository to HACS: HACS ? Integrations ? (?) Custom repositories ? Add (type “Integration”).

Install from HACS, restart HA.

Add YAML config and restart.

11) Known limitations

No UI editor in v0.1.

No per-task holiday handling.

No per-task completion-based reschedule (i.e., cadence is anchored to start_date, not completion).

12) References (for devs)

HA To-Do actions used: todo.get_items, todo.add_item.

Schedule helper: async_track_point_in_utc_time, and local midnight via homeassistant.util.dt.

13) Nice-to-have snippets (future)

Options Flow skeleton (later):

config_flow.py with a form to add tasks, plus an OptionsFlow to edit tasks after setup.

Store tasks in hass.data[DOMAIN] and entry.options.

Per-task time override (later):

Add inject_time: "HH:MM" to task schema; compute the next run at that local time.

ok the roadmap is wrong because we havent even started but here it is
