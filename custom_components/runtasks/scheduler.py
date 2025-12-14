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
