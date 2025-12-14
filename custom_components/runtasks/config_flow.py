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
    return vol.Schema(
        {
            vol.Required(CONF_TASKS, default=default_blob): str,
        }
    )


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
