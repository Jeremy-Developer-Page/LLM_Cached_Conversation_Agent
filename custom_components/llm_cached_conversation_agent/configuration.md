# Configuration reference (LLM Cached Conversation Agent)

Options (editable post-setup from the UI):
- `ollama_base_url` (string): Base URL for the Ollama server, default `http://127.0.0.1:11434`
- `model` (string): LLM model name, default `llama3`
- `system_prompt` (string, optional): A system instruction injected into the LLM backend. If empty, no system prompt is sent.
- `top_p` (float): nucleus sampling probability mass, default 0.9
- `top_k` (int): limit sampling to top-k tokens, default 40
- `repeat_penalty` (float): penalty to discourage repetition, default 1.1
- `min_p` (float): minimum probability threshold (Ollama-specific), default 0.0
- `seed` (int): random seed for generation (-1 means random each time)
- `db_filename` (string): Cache DB file name, default `qa_cache.json`
- `match_punctuation` (boolean): If true (default), questions must match punctuation exactly to hit the cache. If false, punctuation is ignored and alternate forms are added as aliases.
- `include_datetime` (boolean): If true, the current date/time (using Home Assistant's timezone) is appended to the system prompt sent to the LLM. Default `false`.

Data persistence:
- If `db_filename` is a relative path, it will be stored in the integration folder (`config/custom_components/llm_cached_conversation_agent/`).
- The cache is written atomically; malformed files are handled gracefully.
 - The integration maintains two cache variants based on `match_punctuation` (`_true`/`_false`). Toggling the option merges entries so you don't lose data.
