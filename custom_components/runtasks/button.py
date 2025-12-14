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
