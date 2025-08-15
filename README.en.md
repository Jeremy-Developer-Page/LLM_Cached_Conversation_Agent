<p align="center">
  <img src="assets/logo.png" alt="LLM Cached Conversation Agent logo" width="128" height="128" />
</p>

# LLM Cached Conversation Agent (Home Assistant)

A conversational agent for Home Assistant with a local file cache and a LLM (Ollama) fallback for answers not found in the cache.

- Final structure under `config/` in Home Assistant:

```
config/
  custom_components/
  llm_cached_conversation_agent/
      __init__.py
      agent.py
      config_flow.py
      manifest.json
      strings.json
      translations/
        en.json
        it.json
        de.json
        es.json
        fr.json
        pl.json
        pt.json
        el.json
      qa_cache.json  # (optional; created automatically on first use if missing)
```

- Destination path: `config/custom_components/llm_cached_conversation_agent/`
- Copy via Samba (SMB):
  - Windows: `\\homeassistant\\config` or `\\<HA_IP>\\config`
  - macOS: `smb://homeassistant.local/config` or `smb://<HA_IP>/config`
  - Linux: `smb://homeassistant.local/config` or `smb://<HA_IP>/config`

Logo note: place your logo at `assets/logo.png` (PNG, transparent background, ~512×512 recommended).

---

## 1) Hardware and software requirements

- Home Assistant (Core, OS, or Supervised) up and running
- Samba share enabled (or any equivalent method) to access the `config/` folder
- Ollama running and reachable by Home Assistant (default: http://127.0.0.1:11434)
- Suggested resources for models:
  - CPU: recent x86_64/ARMv8 or Raspberry Pi 4/5
  - RAM: depends on the chosen model (e.g., 8 GB recommended for medium models)
  - Disk space: enough for Ollama models and the cache file
- No extra Python dependencies (manifest doesn’t require additional packages)

## 2) Installation on Home Assistant (via Samba: Windows/macOS/Linux)

### 2.1 Enable Samba access
- In HA: Settings → Add-ons → Store → install “Samba share” → configure (user/password) → start.
- After starting, the HA `config/` folder will be accessible over the network (SMB).

### 2.2 Copy the files into the integration folder
- Destination in HA: `config/custom_components/llm_cached_conversation_agent/`
- Copy the whole `custom_components/llm_cached_conversation_agent` folder from this project there.

OS tips:
- Windows: File Explorer → `\\homeassistant\\config` (or `\\<HA_IP>\\config`), go to `custom_components/`, create `llm_cached_conversation_agent`, paste files.
- macOS: Finder → Go → Connect to Server… → `smb://homeassistant.local/config` (or `smb://<HA_IP>/config`) → `custom_components/` → `llm_cached_conversation_agent` → paste files.
- Linux: file manager → `smb://homeassistant.local/config` (or `smb://<HA_IP>/config`), then as above.

### 2.3 Restart Home Assistant
- Settings → System → Restart (or Core only) to load the integration.

### 2.4 Add the integration from the UI
- Settings → Devices & Services → Add Integration → search for “LLM Cached Conversation Agent”.
- Fill in the fields:
  - Ollama Base URL (e.g., `http://127.0.0.1:11434` or container host `http://ollama:11434`)
  - Model (e.g., `llama3`)
  - DB filename (default `qa_cache.json`)

### 2.5 (Optional) Select the agent in Assist
- Settings → Assist → set “Ollama Cached Conversation Agent” as the default agent for the desired language(s).

## 3) Features and supported languages

Main features:
- Local JSON file cache; instant replies when present
- Automatic fallback to Ollama when the cache misses
- Atomic writes and tolerant reads for the cache file (handles partial truncation)
- Configuration via UI (Config Flow)
- Post-configuration changes via UI (Options Flow) with hot apply
- Registers as a Conversation Agent (works with Assist)
- Configurable DB path (default `qa_cache.json` in the integration folder)

Supported languages:
- Conversation/Assist: all languages (agent declares `*` as `supported_languages`)
- Integration UI translations: IT, EN, DE, EL, ES, FR, PL, PT

## 4) How to use

- Ask a question via Assist.
- If the normalized question is in the cache, the agent replies instantly.
- If not, the agent queries Ollama with the configured model, stores the answer in the DB, and returns it.
- To change configuration after installation: Settings → Devices & Services → Integrations → “LLM Cached Conversation Agent” → Configure. Changes (Base URL, Model, DB filename) are applied on the fly.

Manual DB editing (optional):
- Default path: `config/custom_components/llm_cached_conversation_agent/qa_cache.json` (you can change it from Options).
- File structure:
  - `version`: format version
  - `items`: list of objects `{ q, q_norm, a, ts }`
  - `q_norm` is the lookup key (lowercased, whitespace-normalized text).

Useful notes:
- If Ollama runs on another host/container, update the Base URL accordingly and ensure network reachability.
- To reset the cache quickly: stop HA, remove `qa_cache.json`, start HA again: it will be regenerated.
- Logs: Settings → System → Logs (search for `custom_components.llm_cached_conversation_agent`).

## 5) To‑Do (future additions)

- 

---

License: GPL-3.0
