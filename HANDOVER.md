RunTasks - Handover for Codex
0) Mission & Scope

Goal: A Home Assistant custom integration that adds items to existing to-do list entities on a recurring schedule (e.g., "Red Bin every 2nd Tuesday", "Vacuuming every Saturday"), with items appearing at local midnight on their due day.

Out of scope (v0.1):
- Editing/marking to-dos beyond using core todo.* actions.
- Complex calendars/holidays (possible future add-on).

1) Domain, Naming, Versioning

Display name: RunTasks
Python/HA domain (lowercase, no spaces): runtasks
Initial version: v0.1.0
Semantic versioning for releases.

2) Repo Layout (target)
RunTasks/
├─ custom_components/
│  └─ runtasks/
│     ├─ __init__.py
│     ├─ manifest.json
│     ├─ const.py
│     ├─ config_flow.py
│     ├─ scheduler.py
│     ├─ coordinator.py           # (optional for future entities)
│     ├─ config.py                # JSON parsing / validation helpers
│     ├─ button.py                # Run Now button entity
│     ├─ www/runtasks-panel.js    # Built-in panel bundle
│     ├─ strings.json             # (optional for later)
│     └─ translations/            # (optional; for config_flow later)
├─ hacs.json
├─ README.md
├─ CHANGELOG.md
├─ LICENSE
└─ HANDOVER.md                    # this file

HACS: single repo, integration content under custom_components/runtasks/.

3) Minimal Files (v0.1.0)
custom_components/runtasks/manifest.json
{
  "domain": "runtasks",
  "name": "RunTasks",
  "version": "0.1.0",
  "config_flow": true,
  "documentation": "",
  "requirements": [],
  "codeowners": ["@JonCorf"],
  "iot_class": "local_push"
}

Note: leave documentation empty for now (no placeholder links). Add when repo is public.

custom_components/runtasks/const.py
DOMAIN = "runtasks"
CONF_TASKS = "tasks"
DATA_UNSUB = "unsub"
SERVICE_RUN_NOW = "run_now"
DEFAULT_TASKS = [
    {
        "name": "Red bin",
        "list": "todo.house_chores",
        "start_date": "2025-11-18",
        "period_days": 14,
        "weekday": 1,
    },
    {
        "name": "Yellow bin",
        "list": "todo.house_chores",
        "start_date": "2025-11-25",
        "period_days": 14,
        "weekday": 1,
    },
]

# Task keys
K_NAME = "name"
K_LIST = "list"
K_START_DATE = "start_date"     # "YYYY-MM-DD" (local date)
K_PERIOD_DAYS = "period_days"   # int
K_WEEKDAY = "weekday"           # 0=Mon..6=Sun

MIDNIGHT_FMT = "%Y-%m-%d %H:%M:%S"  # due_datetime format

custom_components/runtasks/config.py
from __future__ import annotations
import json
from datetime import datetime
from typing import Any

from .const import K_NAME, K_LIST, K_START_DATE, K_PERIOD_DAYS, K_WEEKDAY

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
            _ = t[K_NAME]
            _ = t[K_LIST]
            _ = datetime.strptime(t[K_START_DATE], "%Y-%m-%d")  # validate
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

custom_components/runtasks/config_flow.py
from __future__ import annotations
import json
from typing import Any

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol

from .config import parse_tasks_blob
from .const import CONF_TASKS, DEFAULT_TASKS, DOMAIN

def _tasks_schema(default_tasks: list[dict[str, Any]] | None) -> vol.Schema:
    default_blob = json.dumps(default_tasks or DEFAULT_TASKS, indent=2)
    return vol.Schema({vol.Required(CONF_TASKS, default=default_blob): str})

class RunTasksConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        placeholders = {"example": json.dumps(DEFAULT_TASKS, indent=2), "error": ""}
        if user_input is not None:
            try:
                tasks = parse_tasks_blob(user_input[CONF_TASKS])
                return self.async_create_entry(title="RunTasks", data={CONF_TASKS: tasks})
            except ValueError as err:
                errors["base"] = "invalid_tasks"
                placeholders["error"] = str(err)

        return self.async_show_form(
            step_id="user",
            data_schema=_tasks_schema(None),
            errors=errors,
            description_placeholders=placeholders,
        )

class RunTasksOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        placeholders = {"example": json.dumps(DEFAULT_TASKS, indent=2), "error": ""}
        current_tasks = self._entry.options.get(CONF_TASKS, self._entry.data.get(CONF_TASKS, []))
        if user_input is not None:
            try:
                tasks = parse_tasks_blob(user_input[CONF_TASKS])
                return self.async_create_entry(title="", data={CONF_TASKS: tasks})
            except ValueError as err:
                errors["base"] = "invalid_tasks"
                placeholders["error"] = str(err)

        return self.async_show_form(
            step_id="init",
            data_schema=_tasks_schema(current_tasks),
            errors=errors,
            description_placeholders=placeholders,
        )

@callback
def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> RunTasksOptionsFlowHandler:
    return RunTasksOptionsFlowHandler(config_entry)

custom_components/runtasks/scheduler.py
from __future__ import annotations
from datetime import datetime, date, time, timedelta
from typing import Callable, Dict, List
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

from .const import MIDNIGHT_FMT, K_NAME, K_LIST, K_START_DATE, K_PERIOD_DAYS, K_WEEKDAY

async def schedule_midnight_daily(hass: HomeAssistant, tasks: List[Dict]) -> Callable[[], None]:
    """Schedule the midnight processor and return a canceller."""
    unsub: Dict[str, Callable[[], None] | None] = {"cancel": None}

    def _schedule_next(local_day_start: datetime) -> None:
        next_utc = dt_util.as_utc(local_day_start)
        unsub["cancel"] = async_track_point_in_utc_time(hass, _run, next_utc)

    async def _run(_now_utc):
        await process_due_tasks(hass, tasks)
        next_local_midnight = dt_util.start_of_local_day(dt_util.now() + timedelta(days=1))
        _schedule_next(next_local_midnight)

    first = dt_util.start_of_local_day(dt_util.now())
    if dt_util.now() >= first + timedelta(minutes=1):
        # already past midnight; run once now then schedule tomorrow
        await process_due_tasks(hass, tasks)
        first = dt_util.start_of_local_day(dt_util.now() + timedelta(days=1))
    _schedule_next(first)

    def cancel() -> None:
        if unsub["cancel"]:
            unsub["cancel"]()
            unsub["cancel"] = None

    return cancel

async def process_due_tasks(hass: HomeAssistant, tasks: List[Dict]):
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

custom_components/runtasks/button.py
from __future__ import annotations
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_TASKS, DOMAIN
from .scheduler import process_due_tasks

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([RunTasksRunNowButton(hass, entry)])

class RunTasksRunNowButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Run Now"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_run_now"

    async def async_press(self) -> None:
        data: dict[str, Any] = self._hass.data.get(DOMAIN, {}).get(self._entry.entry_id, {})
        tasks = data.get(CONF_TASKS, self._entry.data.get(CONF_TASKS, []))
        await process_due_tasks(self._hass, tasks)

custom_components/runtasks/__init__.py
from __future__ import annotations
import logging
from pathlib import Path

from homeassistant.components import frontend, websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol

from .config import validate_tasks
from .const import CONF_TASKS, DATA_UNSUB, DOMAIN, SERVICE_RUN_NOW
from .scheduler import schedule_midnight_daily

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.BUTTON]
PANEL_URL = "runtasks"
STATIC_DIR = Path(__file__).parent / "www"

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    # No YAML support; config entries only.
    if not hass.services.has_service(DOMAIN, SERVICE_RUN_NOW):
        hass.services.async_register(
            DOMAIN,
            SERVICE_RUN_NOW,
            _async_handle_run_now(hass),
            vol.Schema({vol.Optional("entry_id"): str}),
        )
    _register_panel(hass)
    _register_ws(hass)
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    tasks = validate_tasks(entry.options.get(CONF_TASKS, entry.data.get(CONF_TASKS, [])))
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_UNSUB: None, CONF_TASKS: tasks}

    async def _on_started(_):
        cancel = await schedule_midnight_daily(hass, tasks)
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_UNSUB: cancel, CONF_TASKS: tasks}

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_started)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("RunTasks loaded via UI with %d task(s)", len(tasks))
    return True

async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    stored = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if stored and stored.get(DATA_UNSUB):
        stored[DATA_UNSUB]()
    if DOMAIN in hass.data and not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)
    return True

def _async_handle_run_now(hass: HomeAssistant):
    async def handler(call):
        entry_id = call.data.get("entry_id")
        entries = hass.data.get(DOMAIN, {})
        targets = [entry_id] if entry_id else list(entries.keys())
        if not targets:
            _LOGGER.warning("RunTasks run_now: no active config entries")
            return
        from .scheduler import process_due_tasks  # local import to avoid cycle

        for eid in targets:
            data = entries.get(eid)
            if not data:
                _LOGGER.warning("RunTasks run_now: entry_id %s not found", eid)
                continue
            tasks = data.get(CONF_TASKS, [])
            await process_due_tasks(hass, tasks)

    return handler

def _register_panel(hass: HomeAssistant) -> None:
    if STATIC_DIR.exists():
        hass.http.register_static_path("/runtasks-static", str(STATIC_DIR), cache_headers=False)
    frontend.async_register_built_in_panel(
        hass,
        component_name="custom",
        frontend_url_path=PANEL_URL,
        sidebar_title="RunTasks",
        sidebar_icon="mdi:clipboard-text",
        module_url="/runtasks-static/runtasks-panel.js",
        require_admin=True,
        config={"name": "runtasks-panel"},
    )

def _register_ws(hass: HomeAssistant) -> None:
    @websocket_api.websocket_command(
        {
            vol.Required("type"): "runtasks/list",
            vol.Required("entry_id"): str,
        }
    )
    @websocket_api.async_response
    async def ws_list(hass: HomeAssistant, connection, msg):
        entry = hass.config_entries.async_get_entry(msg["entry_id"])
        if not entry:
            connection.send_error(msg["id"], "not_found", "entry not found")
            return
        tasks = entry.options.get(CONF_TASKS, entry.data.get(CONF_TASKS, []))
        connection.send_result(msg["id"], {"tasks": tasks})

    @websocket_api.websocket_command(
        {
            vol.Required("type"): "runtasks/save",
            vol.Required("entry_id"): str,
            vol.Required("tasks"): list,
        }
    )
    @websocket_api.async_response
    async def ws_save(hass: HomeAssistant, connection, msg):
        entry = hass.config_entries.async_get_entry(msg["entry_id"])
        if not entry:
            connection.send_error(msg["id"], "not_found", "entry not found")
            return
        try:
            tasks = validate_tasks(msg["tasks"])
        except ValueError as err:
            connection.send_error(msg["id"], "invalid", str(err))
            return
        hass.config_entries.async_update_entry(entry, options={CONF_TASKS: tasks})
        await hass.config_entries.async_reload(entry.entry_id)
        connection.send_result(msg["id"], {"tasks": tasks})

    @websocket_api.websocket_command(
        {
            vol.Required("type"): "runtasks/run_now",
            vol.Required("entry_id"): str,
        }
    )
    @websocket_api.async_response
    async def ws_run_now(hass: HomeAssistant, connection, msg):
        entry_id = msg["entry_id"]
        entries = hass.data.get(DOMAIN, {})
        data = entries.get(entry_id)
        if not data:
            connection.send_error(msg["id"], "not_found", "entry not loaded")
            return
        from .scheduler import process_due_tasks  # local import to avoid cycle

        await process_due_tasks(hass, data.get(CONF_TASKS, []))
        connection.send_result(msg["id"], {"status": "ok"})

    websocket_api.async_register_command(hass, ws_list)
    websocket_api.async_register_command(hass, ws_save)
    websocket_api.async_register_command(hass, ws_run_now)

custom_components/runtasks/www/runtasks-panel.js
- Panel JS bundle serves the RunTasks admin UI (add/edit/delete, Test Now) via the built-in panel registered at /runtasks.

hacs.json
{
  "name": "RunTasks",
  "content_in_root": false,
  "render_readme": true,
  "domains": ["integration"],
  "homeassistant": "2024.12.0"
}

4) Configuration (UI for v0.1)

Add via HA UI: Settings -> Devices & Services -> Integrations -> Add Integration -> "RunTasks".

Paste tasks JSON when prompted (example):

[
  {
    "name": "Red bin",
    "list": "todo.house_chores",
    "start_date": "2025-11-18",
    "period_days": 14,
    "weekday": 1
  },
  {
    "name": "Yellow bin",
    "list": "todo.house_chores",
    "start_date": "2025-11-25",
    "period_days": 14,
    "weekday": 1
  },
  {
    "name": "Vacuuming",
    "list": "todo.house_chores",
    "start_date": "2025-11-15",
    "period_days": 7,
    "weekday": 5
  }
]

Notes

start_date establishes the cadence anchor (e.g., alternate Tuesdays).

Items are injected with due_datetime at 00:00 local time on due days.

Duplicate prevention: we only add the item if there is no existing needs_action item with the same summary in that list.

5) Dev Workflow (VS Code + HA)

Clone repo into your HA /config (or mount).

Ensure path is custom_components/runtasks/....

Restart HA, then add the integration via UI and paste tasks JSON.

Open the RunTasks panel from the sidebar (/runtasks) to add/edit/delete tasks and hit "Test Now".

Verify logs: "RunTasks loaded via UI with %d task(s)".

Create/identify a to-do list entity (e.g., Local To-do -> todo.house_chores).

(Dev) Temporarily change weekday/start_date in the panel or Options to force a due condition and confirm item injection by running Test Now or advancing system date/time in a test env.

6) Acceptance Criteria (v0.1)

- On the first HA start after install, RunTasks schedules itself to run at local midnight and re-schedules daily thereafter.
- On a due day, an item with the configured name is added to the target todo entity at 00:00 local time with due_datetime set to midnight.
- Duplicate items are not created if a needs_action item with the same summary already exists.
- Supports at least 40 tasks without separate automations.
- Run Now button/service and panel Test Now trigger the same logic immediately.

7) Test Plan (manual)

Unit cadence: Use two bin tasks with 14-day periods and staggered start_dates a week apart; verify they alternate Tuesdays.

Weekly task: Vacuuming with period_days: 7 on weekday: 5; verify every Saturday.

Duplicate prevention: Pre-create Red bin in the list and run midnight job; ensure no second item is added.

Time zone: Confirm midnight is taken from HA local timezone (Sydney), not UTC.

Run Now: Press button entity, panel Test Now, or call service runtasks.run_now and verify immediate injection when due.

8) Roadmap

v0.1.0 (current): UI config flow + options, built-in panel (add/edit/delete + Test Now), Run Now button/service, midnight scheduler, duplicate prevention, HACS-installable.

v0.2.0: Per-task inject time override, optional pre-notice (e.g., T-1 day).

v0.3.0: Entity exposure (e.g., sensors with next due date per task), pause/resume toggles, holiday offsets (optional).

v0.4.0: Import/export tasks, migration helpers, tests.

9) Coding Guidelines

Async-first; use hass.services.async_call(..., blocking=True) only where needed.

Strict validation of JSON input (see config.py).

No placeholder links in docs.

Keep logs informative but sparse (one info on load, warning on invalid config).

10) HACS Release Steps

Commit + tag: v0.1.0.

Add repository to HACS: HACS -> Integrations -> (...) Custom repositories -> Add (type "Integration").

Install from HACS, restart HA.

Add config via UI and restart.

11) Known limitations

No per-task holiday handling.

No per-task completion-based reschedule (cadence is anchored to start_date, not completion).

JSON text input in config/Options (no per-field form yet).

12) References (for devs)

HA To-Do actions used: todo.get_items, todo.add_item.

Schedule helper: async_track_point_in_utc_time, and local midnight via homeassistant.util.dt.

13) Nice-to-have snippets (future)

Per-task time override (later):

Add inject_time: "HH:MM" to task schema; compute the next run at that local time.

Entity exposure (later): sensors with next due per task and pause/resume toggles.
