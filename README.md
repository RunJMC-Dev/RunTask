# RunTasks

RunTasks is a Home Assistant custom integration that drops recurring to-do items into existing `todo` entities at local midnight. Configured entirely via the HA UI (no YAML) with a built-in panel for editing tasks.

## Features (v0.1 target)
- Midnight injector: adds items on their due day at 00:00 local time.
- Recurring cadence: anchor with `start_date` + `period_days` (e.g., every 14 days from the start date).
- Duplicate guard: skips if a `needs_action` item with the same summary already exists.
- UI config: paste a JSON list of tasks in the config flow; edit later via Options.
- Built-in panel: add/edit/delete tasks in the RunTasks sidebar page, with a **Test Now** button.
- Run Now button: HA exposes a `RunTasks: Run Now` button entity to trigger immediately (or call the `runtasks.run_now` service).
- Lightweight: HACS-installable.

## Install
1. Drop the repo into Home Assistant `/config` so files land under `custom_components/runtasks/` (or add as a custom repository in HACS once published).
2. Restart Home Assistant.

## Configuration (UI)
1. Settings → Devices & Services → Integrations → Add Integration → search “RunTasks”.
2. Paste tasks as JSON when prompted (example below).
3. Edit tasks in the RunTasks sidebar panel (`/runtasks`) with add/edit/delete controls and a Test Now button.

```yaml
[
  {
    "name": "Red bin",
    "list": "todo.house_chores",
    "start_date": "2025-11-18",
    "period_days": 14
  },
  {
    "name": "Yellow bin",
    "list": "todo.house_chores",
    "start_date": "2025-11-25",
    "period_days": 14
  },
  {
    "name": "Vacuuming",
    "list": "todo.house_chores",
    "start_date": "2025-11-15",
    "period_days": 7
  }
]
```

Notes:
- `start_date` is the cadence anchor (items repeat every `period_days` from that date).
- Items are added at local midnight on due days.
- We only add if there is no existing `needs_action` item with the same summary in that list.

## How it works
- On HA start, RunTasks validates tasks and schedules a daily run at local midnight.
- On each run, it checks tasks due that day and calls `todo.get_items` then `todo.add_item` to inject the to-dos with `due_datetime` set to midnight.
- A `RunTasks: Run Now` button entity (and `runtasks.run_now` service) let you trigger the same logic immediately.

## Dev workflow
- Place the repo under `/config/custom_components/runtasks/` in your HA environment and restart HA.
- Add the integration through the UI, paste tasks JSON, and save.
- Open the RunTasks panel from the sidebar (`/runtasks`) to add/edit/delete tasks and hit **Test Now**.
- Watch logs for: `RunTasks loaded via UI with X task(s)`.
- For quick testing, use the RunTasks panel **Test Now** button, the `RunTasks: Run Now` button entity, or tweak `period_days`/`start_date` in Options.

## Acceptance criteria (v0.1)
- Schedules at local midnight after first HA start and reschedules daily.
- On due days, adds the item with `due_datetime` at 00:00 local time.
- No duplicates when a matching `needs_action` item already exists.
- Handles 40+ tasks without extra automations.

## Roadmap
- v0.1.0: UI config flow + options, Run Now button, midnight scheduler, duplicate prevention, HACS-installable.
- v0.2.0: Per-task inject time override, optional pre-notice (e.g., T-1 day).
- v0.3.0: Entities (next due per task), pause/resume toggles, holiday offsets.
- v0.4.0: Import/export tasks, migration helpers, tests.

## Limitations
- JSON text entry (no per-task form/validation beyond JSON parse).
- No holiday handling.
- Cadence anchored to `start_date` (not completion-based reschedule).

## License
Private / all rights reserved.
