"""LLM Cached Conversation Agent integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from homeassistant.components.conversation.agent_manager import get_agent_manager

from .agent import LLMCachedAgent

DOMAIN = "llm_cached_conversation_agent"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Merge data + options (options override data)
    merged = {**entry.data, **entry.options}
    agent = LLMCachedAgent(hass, merged)
    manager = get_agent_manager(hass)
    manager.async_set_agent(entry.entry_id, agent)
    # Keep reference to agent instance for option updates
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = agent
    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    manager = get_agent_manager(hass)
    manager.async_unset_agent(entry.entry_id)
    # Cleanup stored agent reference
    domain_data = hass.data.get(DOMAIN)
    if isinstance(domain_data, dict):
        domain_data.pop(entry.entry_id, None)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update by applying new config to existing agent."""
    domain_data = hass.data.get(DOMAIN, {})
    agent: LLMCachedAgent | None = domain_data.get(entry.entry_id)
    if agent is None:
        return
    merged = {**entry.data, **entry.options}
    await agent.async_update_config(merged)
