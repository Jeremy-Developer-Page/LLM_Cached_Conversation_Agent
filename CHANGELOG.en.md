# Changelog (English)

## 1.3 2025/08/19
New features:
- New `include_datetime` option: when enabled, the agent appends the current date/time (using Home Assistant's timezone) to the system prompt sent to Ollama. Useful for time-sensitive queries (e.g., “what day is it today?”).
- UI and translations updated (IT/EN/DE/EL/ES/FR/PL/PT) for the new toggle.
- Documentation updated in `configuration.md`.

## 1.2 2025/08/15
New features:
- Optional system prompt sent to Ollama (as `system` in the generate API)
- Sampling controls in `options` for Ollama:
  - `top_p` (nucleus sampling, default 0.9)
  - `top_k` (default 40)
  - `repeat_penalty` (default 1.1)
  - `min_p` (default 0.0)
  - `seed` (default -1 = random)
- UI and translations (IT/EN) updated for the new fields
- Documentation updated in `configuration.md`

## 1.1 2025/08/15
Additions and changes:
- `match_punctuation` option for cache lookup:
  - When `true` (default), lookup requires exact punctuation match
  - When `false`, punctuation is ignored; alternate forms are recorded as aliases
- Robust handling when toggling `match_punctuation`:
  - Safe merge between `_true`/`_false` cache variants to prevent data loss
  - Read/validate both variant files before reload
  - Atomic writes and I/O locking to avoid race conditions

## 1.0 2025/08/15
Initial features (everything except `match_punctuation`):
- Conversation Agent for Home Assistant (Assist-compatible)
- Local JSON file cache with instant responses when present
- Automatic fallback to Ollama when the answer is not in cache
- Atomic cache writes and tolerant reads for partially truncated files
- UI configuration (Config Flow) and post-setup editing (Options Flow) applied live
- Configurable DB path (default `qa_cache.json` in the integration folder)
- Supported conversation languages: all (`supported_languages = "*"`)
- UI translations available (IT, EN, DE, EL, ES, FR, PL, PT)
