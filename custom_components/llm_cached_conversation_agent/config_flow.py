"""Config flow for LLM Cached Conversation Agent."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from . import DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(title="LLM Cached Conversation Agent", data=user_input)

        schema = vol.Schema(
            {
                vol.Required("ollama_base_url", default="http://127.0.0.1:11434"): str,
                vol.Required("model", default="llama3"): str,
                vol.Optional("system_prompt", default=""): str,
                vol.Optional("top_p", default=0.9): vol.Coerce(float),
                vol.Optional("top_k", default=40): vol.Coerce(int),
                vol.Optional("repeat_penalty", default=1.1): vol.Coerce(float),
                vol.Optional("min_p", default=0.0): vol.Coerce(float),
                vol.Optional("seed", default=-1): vol.Coerce(int),
                vol.Optional("db_filename", default="qa_cache.json"): str,
                vol.Optional("match_punctuation", default=True): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        # Avoid setting `config_entry` attribute directly (deprecated).
        # Store it on a private attribute instead.
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        # Merge: options override data so the form shows the latest saved values
        data = {**self._config_entry.data, **self._config_entry.options}
        schema = vol.Schema(
            {
                vol.Required("ollama_base_url", default=data.get("ollama_base_url", "http://127.0.0.1:11434")): str,
                vol.Required("model", default=data.get("model", "llama3")): str,
                vol.Optional("system_prompt", default=data.get("system_prompt", "")): str,
                vol.Optional("top_p", default=data.get("top_p", 0.9)): vol.Coerce(float),
                vol.Optional("top_k", default=data.get("top_k", 40)): vol.Coerce(int),
                vol.Optional("repeat_penalty", default=data.get("repeat_penalty", 1.1)): vol.Coerce(float),
                vol.Optional("min_p", default=data.get("min_p", 0.0)): vol.Coerce(float),
                vol.Optional("seed", default=data.get("seed", -1)): vol.Coerce(int),
                vol.Optional("db_filename", default=data.get("db_filename", "qa_cache.json")): str,
                vol.Optional("match_punctuation", default=data.get("match_punctuation", True)): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
