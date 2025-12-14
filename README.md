# RunTasks

RunTasks is a Home Assistant custom integration that drops recurring to-do items into existing `todo` entities at local midnight. YAML-only for v0.1, no UI yet.

## Features (v0.1 target)
- Midnight injector: adds items on their due day at 00:00 local time.
- Recurring cadence: anchor with `start_date` + `weekday` + `period_days` (e.g., every 14 days on Tuesday).
- Duplicate guard: skips if a `needs_action` item with the same summary already exists.
- Lightweight: YAML config only; HACS-installable.

## Install
1. Drop the repo into Home Assistant `/config` so files land under `custom_components/runtasks/` (or add as a custom repository in HACS once published).
2. Restart Home Assistant.

## Configuration (YAML)
Add to `configuration.yaml`:

```yaml
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
```

Notes:
- `start_date` is the cadence anchor (e.g., alternating Tuesdays).
- Items are added at local midnight on due days.
- We only add if there is no existing `needs_action` item with the same summary in that list.

## How it works
- On HA start, RunTasks validates tasks and schedules a daily run at local midnight.
- On each run, it checks tasks due that day and calls `todo.get_items` then `todo.add_item` to inject the to-dos with `due_datetime` set to midnight.

## Dev workflow
- Place the repo under `/config/custom_components/runtasks/` in your HA environment.
- Settings ? Devices & Services ? Check Config, then restart.
- Watch logs for: `RunTasks loaded with X task(s)`.
- For quick testing, temporarily tweak `weekday`/`start_date` to force a due condition and observe the target to-do list.

## Acceptance criteria (v0.1)
- Schedules at local midnight after first HA start and reschedules daily.
- On due days, adds the item with `due_datetime` at 00:00 local time.
- No duplicates when a matching `needs_action` item already exists.
- Handles 40+ tasks without extra automations.

## Roadmap
- v0.1.0: YAML config, midnight scheduler, duplicate prevention, HACS-installable.
- v0.2.0: Config Flow + Options Flow, per-task inject time override, optional pre-notice (e.g., T-1 day).
- v0.3.0: Entities (next due per task), pause/resume toggles, holiday offsets.
- v0.4.0: Import/export tasks, migration helpers, tests.

## Limitations
- No UI editor in v0.1.
- No holiday handling.
- Cadence anchored to `start_date` (not completion-based reschedule).

## License
Private / all rights reserved.
