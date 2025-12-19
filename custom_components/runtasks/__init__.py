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
PANEL_VERSION = "1.0.1"  # bump to bust cached panel assets when UI changes
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

    if hass.is_running:
        await _on_started(None)
    else:
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
        register_static = getattr(hass.http, "register_static_path", None)
        if register_static:
            register_static("/runtasks-static", str(STATIC_DIR), cache_headers=False)
        else:
            try:
                # Fallback for HA versions where register_static_path is removed
                hass.http.app.router.add_static("/runtasks-static", str(STATIC_DIR))
            except Exception as err:  # pragma: no cover - defensive logging
                _LOGGER.error("Failed to register RunTasks static path: %s", err)
                return
    frontend.async_register_built_in_panel(
        hass,
        component_name="custom",
        frontend_url_path=PANEL_URL,
        sidebar_title="RunTasks",
        sidebar_icon="mdi:clipboard-text",
        require_admin=True,
        config={
            "_panel_custom": {
                "name": "runtasks-panel",
                "module_url": f"/runtasks-static/runtasks-panel.js?v={PANEL_VERSION}",
                "embed_iframe": False,
                "trust_external": False,
            }
        },
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
