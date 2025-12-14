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
