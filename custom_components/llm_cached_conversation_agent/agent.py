"""LLM Cached Conversation Agent implementation."""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.components.conversation.models import (
    AbstractConversationAgent,
    ConversationInput,
    ConversationResult,
)
from homeassistant.helpers import intent


@dataclass
class CacheItem:
    q: str
    q_norm: str
    a: str
    ts: str


def normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


class LLMCachedAgent(AbstractConversationAgent):
    """Conversation agent with file cache and LLM fallback via Ollama."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        self.hass = hass
        self.config = config
        self._cache: dict[str, CacheItem] = {}
        self._cache_path: Path = Path(config.get("db_filename", "qa_cache.json"))
        if not self._cache_path.is_absolute():
            # Put DB inside integration folder by default
            self._cache_path = Path(__file__).parent / self._cache_path
        self._ollama_url: str = config.get("ollama_base_url", "http://127.0.0.1:11434")
        self._model: str = config.get("model", "llama3")
        self._io_lock = asyncio.Lock()

    @property
    def supported_languages(self) -> list[str] | str:
        # Match all languages by default
        return "*"

    async def async_prepare(self, language: str | None = None) -> None:
        await self.hass.async_add_executor_job(self._load_cache)

    async def async_reload(self, language: str | None = None) -> None:
        await self.hass.async_add_executor_job(self._load_cache)

    async def async_update_config(self, config: dict[str, Any]) -> None:
        """Apply new configuration at runtime and refresh cache path if changed."""
        # Update config dict
        self.config = config
        # Update derived fields
        self._ollama_url = config.get("ollama_base_url", self._ollama_url)
        self._model = config.get("model", self._model)
        new_path_cfg = config.get("db_filename", self._cache_path.name)
        new_path = Path(new_path_cfg)
        if not new_path.is_absolute():
            new_path = Path(__file__).parent / new_path
        # If path changed, swap and (lazily) load
        path_changed = new_path != self._cache_path
        if path_changed:
            self._cache_path = new_path
        # Reload cache contents (safe even if same path)
        await self.hass.async_add_executor_job(self._load_cache)

    def _read_json_tolerant(self, path: Path) -> dict[str, Any] | None:
        """Read JSON from path, tolerant to trailing NULs/garbage.

        Returns None if unrecoverable.
        """
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            return {"version": 1, "items": []}
        except Exception:
            return None

        # Strip trailing NULs and whitespace
        stripped = raw.rstrip(b"\x00\r\n\t ")
        if not stripped:
            return {"version": 1, "items": []}
        try:
            return json.loads(stripped.decode("utf-8"))
        except Exception:
            # Try to cut to last closing curly brace
            try:
                txt = stripped.decode("utf-8", errors="ignore")
                last = txt.rfind("}")
                if last != -1:
                    return json.loads(txt[: last + 1])
            except Exception:
                return None
        return None

    def _ensure_parent(self) -> None:
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def _load_cache(self) -> None:
        # Protected by lock at call sites via executor serialization
        try:
            self._ensure_parent()
            data = self._read_json_tolerant(self._cache_path)
            if not data:
                # Create empty DB file atomically
                self._atomic_write(json.dumps({"version": 1, "items": []}, ensure_ascii=False, indent=2))
                self._cache = {}
                return
            self._cache = {
                item.get("q_norm", ""): CacheItem(
                    q=item.get("q", ""),
                    q_norm=item.get("q_norm", ""),
                    a=item.get("a", ""),
                    ts=item.get("ts", ""),
                )
                for item in data.get("items", [])
                if item.get("q_norm")
            }
        except Exception:
            # Keep running even if DB is malformed
            self._cache = {}

    def _atomic_write(self, text: str) -> None:
        """Atomically write text to cache file to avoid truncation/corruption."""
        try:
            self._ensure_parent()
            tmp_path = self._cache_path.with_suffix(self._cache_path.suffix + ".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self._cache_path)
        except Exception:
            # As last resort, try simple write (may still fail)
            try:
                self._cache_path.write_text(text, encoding="utf-8")
            except Exception:
                pass

    def _save_cache(self) -> None:
        try:
            items = [vars(ci) for ci in self._cache.values()]
            data = {"version": 1, "items": items}
            payload = json.dumps(data, ensure_ascii=False, indent=2)
            self._atomic_write(payload)
        except Exception:
            pass

    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        q = user_input.text
        qn = normalize(q)

        # 1) Cache
        if qn in self._cache:
            resp = intent.IntentResponse(language=user_input.language)
            resp.async_set_speech(self._cache[qn].a)
            return ConversationResult(response=resp, conversation_id=user_input.conversation_id)

        # 2) Fallback to LLM via Ollama
        answer = await self._ask_llm(q)

        if answer:
            # 3) Save to cache (guarded by lock)
            now = datetime.now(timezone.utc).isoformat()
            async with self._io_lock:
                self._cache[qn] = CacheItem(q=q, q_norm=qn, a=answer, ts=now)
                await self.hass.async_add_executor_job(self._save_cache)

        resp = intent.IntentResponse(language=user_input.language)
        resp.async_set_speech(answer or "Mi dispiace, non ho trovato una risposta.")
        return ConversationResult(response=resp, conversation_id=user_input.conversation_id)

    async def _ask_llm(self, prompt: str) -> str | None:
        # For now, use Ollama generate API as the LLM backend
        import aiohttp  # type: ignore

        url = f"{self._ollama_url.rstrip('/')}/api/generate"
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=60) as r:
                    if r.status != 200:
                        return None
                    data = await r.json()
                    return data.get("response")
        except Exception:
            return None
