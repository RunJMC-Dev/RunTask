from __future__ import annotations
import logging

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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    # No YAML support; config entries only.
    if not hass.services.has_service(DOMAIN, SERVICE_RUN_NOW):
        hass.services.async_register(
            DOMAIN,
            SERVICE_RUN_NOW,
            _async_handle_run_now(hass),
            vol.Schema({vol.Optional("entry_id"): str}),
        )
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
