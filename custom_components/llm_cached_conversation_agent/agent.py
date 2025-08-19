"""LLM Cached Conversation Agent implementation."""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

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
    # List of alternate normalized forms (keeps variants like with/without punctuation)
    aliases: list[str] = field(default_factory=list)


def normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _strip_punctuation(text: str) -> str:
    """Return text without punctuation (keeps letters, numbers and spaces)."""
    # Keep unicode alphanumeric characters and whitespace
    return "".join(ch for ch in text if ch.isalnum() or ch.isspace())


class LLMCachedAgent(AbstractConversationAgent):
    """Conversation agent with file cache and LLM fallback via Ollama."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        self.hass = hass
        self.config = config
        self._cache: dict[str, CacheItem] = {}
        # Base filename (used to derive _true / _false variants)
        self._base_cache_path: Path = Path(config.get("db_filename", "qa_cache.json"))
        if not self._base_cache_path.is_absolute():
            # Put DB inside integration folder by default
            self._base_cache_path = Path(__file__).parent / self._base_cache_path
        # Ensure both variant files exist (create if missing) so toggling
        # match_punctuation won't find missing files later. Create files
        # conservatively only when they don't exist.
        try:
            default_payload = json.dumps({"version": 1, "items": []}, ensure_ascii=False, indent=2)
            for m in (True, False):
                p = self._cache_filename_for(m)
                try:
                    self._ensure_parent(p)
                    if not p.exists():
                        # write atomically to avoid partial files
                        self._atomic_write(default_payload, path=p)
                except Exception:
                    # best-effort: skip creation on failure
                    continue
        except Exception:
            pass
        self._ollama_url: str = config.get("ollama_base_url", "http://127.0.0.1:11434")
        self._model: str = config.get("model", "llama3")
        self._system_prompt: str = config.get("system_prompt", "")
        self._include_datetime: bool = bool(config.get("include_datetime", False))
        self._top_p: float = float(config.get("top_p", 0.9))
        self._top_k: int = int(config.get("top_k", 40))
        self._repeat_penalty: float = float(config.get("repeat_penalty", 1.1))
        self._min_p: float = float(config.get("min_p", 0.0))
        self._seed: int = int(config.get("seed", -1))
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
        # If the only changed option is `match_punctuation`, avoid any
        # path/model updates or writes: just update config in memory and
        # reload the cache from disk. This prevents toggling the option
        # from causing unintended side-effects.
        prev_match = bool(self.config.get("match_punctuation", True))
        new_match = bool(config.get("match_punctuation", prev_match))

        # If the match_punctuation toggle changed, just update config in
        # memory and reload the cache from disk. Do not touch paths or
        # perform any writes — this prevents toggling from resetting DB.
        if prev_match != new_match:
            # Merge data from the previously active file into the newly active
            # file so toggling does not lose existing entries.
            prev_path = self._cache_filename_for(prev_match)
            new_path = self._cache_filename_for(new_match)
            # Acquire IO lock to avoid races with concurrent saves/alias-updates
            # while we merge and reload cache files.
            async with self._io_lock:
                # Perform merge on executor to avoid blocking the event loop
                await self.hass.async_add_executor_job(self._merge_cache_files, prev_path, new_path)
                # Touch/read both variant files on the executor to ensure they
                # are readable and not corrupted (best-effort). This helps
                # avoid later surprises when the active file is read/written.
                await self.hass.async_add_executor_job(self._read_json_tolerant, prev_path)
                await self.hass.async_add_executor_job(self._read_json_tolerant, new_path)
                # Update runtime config and reload the active cache
                self.config = config
                await self.hass.async_add_executor_job(self._load_cache)
            return

        # Update config in memory for other changes
        self.config = config

        # Otherwise, proceed to update derived fields and potentially change path
        self._ollama_url = config.get("ollama_base_url", self._ollama_url)
        self._model = config.get("model", self._model)
        self._system_prompt = config.get("system_prompt", self._system_prompt)
        self._include_datetime = bool(config.get("include_datetime", self._include_datetime))
        self._top_p = float(config.get("top_p", self._top_p))
        self._top_k = int(config.get("top_k", self._top_k))
        self._repeat_penalty = float(config.get("repeat_penalty", self._repeat_penalty))
        self._min_p = float(config.get("min_p", self._min_p))
        self._seed = int(config.get("seed", self._seed))
        new_path_cfg = config.get("db_filename", self._base_cache_path.name)
        new_path = Path(new_path_cfg)
        if not new_path.is_absolute():
            new_path = Path(__file__).parent / new_path
        # If path changed, swap and (lazily) load
        path_changed = new_path != self._base_cache_path
        if path_changed:
            self._base_cache_path = new_path
        # Reload cache contents (safe even if same path)
        await self.hass.async_add_executor_job(self._load_cache)

    def _cache_filename_for(self, match: bool) -> Path:
        """Return the cache Path for the given match_punctuation value.

        Example: base 'qa_cache.json' -> 'qa_cache_true.json' / 'qa_cache_false.json'.
        """
        base = self._base_cache_path
        stem = base.stem
        suffix = base.suffix
        tag = "true" if match else "false"
        if suffix:
            name = f"{stem}_{tag}{suffix}"
        else:
            name = f"{base.name}_{tag}"
        return base.parent / name

    def _active_cache_path(self) -> Path:
        return self._cache_filename_for(bool(self.config.get("match_punctuation", True)))

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

    def _merge_cache_files(self, src: Path, dst: Path) -> None:
        """Merge entries from src into dst without duplicating q_norm.

        If dst doesn't exist, it will be created as a copy of src. If it exists,
        entries from src that don't have a matching q_norm in dst will be appended.
        """
        try:
            self._ensure_parent(dst)
            # Create a single backup of the destination before merging.
            # This overwrite any existing .bak for that cache so we keep
            # at most one backup per cache file.
            try:
                if dst.exists():
                    # Use base cache filename for the bak so it doesn't include
                    # the _true/_false variant (keep one bak per DB base).
                    base = self._base_cache_path
                    bak = base.with_name(base.name + ".bak")
                    try:
                        self._ensure_parent(bak)
                        bak.write_bytes(dst.read_bytes())
                    except Exception:
                        # As fallback, attempt atomic text write
                        try:
                            payload = dst.read_text(encoding="utf-8", errors="ignore")
                            self._ensure_parent(bak)
                            self._atomic_write(payload, path=bak)
                        except Exception:
                            pass
            except Exception:
                # If backup cannot be created, continue — merge is best-effort
                pass

            src_data = self._read_json_tolerant(src)
            if not src_data:
                return
            dst_data = self._read_json_tolerant(dst)
            if dst_data is None:
                # If dst is unreadable, skip merge to avoid data loss
                return

            src_items = src_data.get("items", [])
            dst_items = dst_data.get("items", [])
            existing_qnorms = {item.get("q_norm") for item in dst_items if item.get("q_norm")}

            appended = False
            for item in src_items:
                qn = item.get("q_norm")
                if not qn:
                    continue
                if qn in existing_qnorms:
                    continue
                dst_items.append(item)
                appended = True

            if appended:
                payload = json.dumps({"version": 1, "items": dst_items}, ensure_ascii=False, indent=2)
                # ensure parent exists
                self._ensure_parent(dst)
                # write to dst atomically
                self._atomic_write(payload, path=dst)
        except Exception:
            # don't raise — merging is best-effort
            return

    def _ensure_parent(self, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def _load_cache(self) -> None:
        # Protected by lock at call sites via executor serialization
        try:
            path = self._active_cache_path()
            self._ensure_parent(path)
            # If file doesn't exist yet, don't create/overwrite it here; keep cache empty
            if not path.exists():
                self._cache = {}
                return

            data = self._read_json_tolerant(path)
            # If reading failed unrecoverably, keep existing cache and do not overwrite file
            if data is None:
                return
            self._cache = {
                item.get("q_norm", ""): CacheItem(
                    q=item.get("q", ""),
                    q_norm=item.get("q_norm", ""),
                    a=item.get("a", ""),
                    ts=item.get("ts", ""),
                    aliases=item.get("aliases", []) or [],
                )
                for item in data.get("items", [])
                if item.get("q_norm")
            }
        except Exception:
            # Keep running even if DB is malformed
            self._cache = {}

    def _atomic_write(self, text: str, path: Path | None = None) -> None:
        """Atomically write text to cache file to avoid truncation/corruption."""
        try:
            # Use explicit path passed via callers (use _active_cache_path when needed)
            # Caller should ensure parent exists.
            target = path or self._active_cache_path()
            tmp_path = target.with_suffix(target.suffix + ".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, target)
        except Exception:
            # As last resort, try simple write (may still fail)
            try:
                (path or self._active_cache_path()).write_text(text, encoding="utf-8")
            except Exception:
                pass

    def _save_cache(self) -> None:
        try:
            # Do not overwrite the on-disk DB with an empty list if the
            # in-memory cache is empty. This prevents accidental resets
            # (for example during config updates or startup) that would
            # otherwise erase stored data.
            if not self._cache:
                return

            items = [vars(ci) for ci in self._cache.values()]
            data = {"version": 1, "items": items}
            payload = json.dumps(data, ensure_ascii=False, indent=2)
            # ensure parent exists for active path
            active = self._active_cache_path()
            self._ensure_parent(active)
            # Pass explicit path to avoid races where _active_cache_path()
            # could change between computing `active` and performing the
            # atomic write (for example due to concurrent config toggles).
            self._atomic_write(payload, path=active)
        except Exception:
            pass

    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        q = user_input.text
        qn = normalize(q)
        # Whether to require punctuation to match. Default True to preserve
        # existing behaviour (exact punctuation match).
        match_punctuation = bool(self.config.get("match_punctuation", True))

        # 1) Cache
        if match_punctuation:
            # Require exact normalized match (including punctuation)
            if qn in self._cache:
                resp = intent.IntentResponse(language=user_input.language)
                resp.async_set_speech(self._cache[qn].a)
                return ConversationResult(response=resp, conversation_id=user_input.conversation_id)
        else:
            # When ignoring punctuation, prefer exact match but fall back
            # to punctuation-insensitive comparison (including aliases).
            if qn in self._cache:
                resp = intent.IntentResponse(language=user_input.language)
                resp.async_set_speech(self._cache[qn].a)
                return ConversationResult(response=resp, conversation_id=user_input.conversation_id)

            qn_cmp = _strip_punctuation(qn)
            found_key: str | None = None
            found: CacheItem | None = None
            for k, ci in self._cache.items():
                # check primary normalized form
                if _strip_punctuation(ci.q_norm) == qn_cmp:
                    found_key = k
                    found = ci
                    break
                # check aliases
                for alias in (ci.aliases or []):
                    if _strip_punctuation(alias) == qn_cmp:
                        found_key = k
                        found = ci
                        break
                if found:
                    break
            if found:
                # If the normalized form isn't recorded yet as primary or alias,
                # and match_punctuation is False, add it to aliases and save,
                # but do NOT change the stored answer.
                if qn != found.q_norm and qn not in (found.aliases or []):
                    async with self._io_lock:
                        # reload reference in case of race
                        if found_key is not None:
                            key = found_key
                            ci = self._cache.get(key)
                            if ci is not None:
                                if qn != ci.q_norm and qn not in (ci.aliases or []):
                                    ci.aliases.append(qn)
                                    self._cache[key] = ci
                                    await self.hass.async_add_executor_job(self._save_cache)

                resp = intent.IntentResponse(language=user_input.language)
                resp.async_set_speech(found.a)
                return ConversationResult(response=resp, conversation_id=user_input.conversation_id)

        # 2) Fallback to LLM via Ollama
        answer = await self._ask_llm(q)

        if answer:
            # 3) Save to cache (guarded by lock)
            now = datetime.now(timezone.utc).isoformat()
            async with self._io_lock:
                if match_punctuation:
                    # When punctuation matching is required, always create a
                    # new record for this exact normalized form (do not merge
                    # with stripped matches or aliases).
                    self._cache[qn] = CacheItem(q=q, q_norm=qn, a=answer, ts=now, aliases=[])
                else:
                    # When ignoring punctuation, check again for an existing
                    # stripped match. If found, add qn as alias if missing
                    # but DO NOT overwrite the stored answer.
                    qn_cmp = _strip_punctuation(qn)
                    existing_key: str | None = None
                    for k, ci in self._cache.items():
                        if _strip_punctuation(ci.q_norm) == qn_cmp:
                            existing_key = k
                            break
                        for alias in (ci.aliases or []):
                            if _strip_punctuation(alias) == qn_cmp:
                                existing_key = k
                                break
                        if existing_key:
                            break

                    if existing_key is not None:
                        ci = self._cache[existing_key]
                        if qn != ci.q_norm and qn not in (ci.aliases or []):
                            ci.aliases.append(qn)
                            self._cache[existing_key] = ci
                        # Do NOT change ci.a or ci.ts when merging aliases
                    else:
                        # No similar entry: create new record
                        self._cache[qn] = CacheItem(q=q, q_norm=qn, a=answer, ts=now, aliases=[])

                await self.hass.async_add_executor_job(self._save_cache)

        resp = intent.IntentResponse(language=user_input.language)
        resp.async_set_speech(answer or "Mi dispiace, non ho trovato una risposta.")
        return ConversationResult(response=resp, conversation_id=user_input.conversation_id)

    async def _ask_llm(self, prompt: str) -> str | None:
        # For now, use Ollama generate API as the LLM backend
        import aiohttp  # type: ignore

        url = f"{self._ollama_url.rstrip('/')}/api/generate"
        # Build system prompt (optionally include current date/time)
        system_prompt = self._system_prompt or ""
        if self._include_datetime:
            try:
                dt = self._current_datetime_string()
                extra = f"Current date/time: {dt}"
            except Exception:
                extra = None
            if extra:
                system_prompt = (system_prompt + "\n\n" if system_prompt else "") + extra

        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
        }
        if system_prompt:
            # Ollama's generate API accepts a 'system' field to set a system prompt
            payload["system"] = system_prompt
        # Optional generation options
        options: dict[str, Any] = {}
        options["top_p"] = self._top_p
        options["top_k"] = self._top_k
        options["repeat_penalty"] = self._repeat_penalty
        options["min_p"] = self._min_p
        if self._seed is not None:
            options["seed"] = self._seed
        if options:
            payload["options"] = options
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as r:
                    if r.status != 200:
                        return None
                    data = await r.json()
                    return data.get("response")
        except Exception:
            return None

    def _current_datetime_string(self) -> str:
        """Return current date/time as ISO string with timezone info.

        Preference is the Home Assistant configured timezone; fallback to UTC.
        """
        try:
            tz_name = getattr(self.hass.config, "time_zone", None)
            tz = ZoneInfo(tz_name) if tz_name else timezone.utc
        except Exception:
            tz = timezone.utc
        now = datetime.now(tz).replace(microsecond=0)
        # Example: 2025-08-19T14:22:05+02:00 (Europe/Rome)
        tz_label = getattr(tz, "key", None) or getattr(tz, "tzname", lambda *_: "")(now) or "UTC"
        return f"{now.isoformat()} ({tz_label})"
