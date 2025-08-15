# Configuration reference (LLM Cached Conversation Agent)

Options (editable post-setup from the UI):
- `ollama_base_url` (string): Base URL for the Ollama server, default `http://127.0.0.1:11434`
- `model` (string): LLM model name, default `llama3`
- `db_filename` (string): Cache DB file name, default `qa_cache.json`

Data persistence:
- If `db_filename` is a relative path, it will be stored in the integration folder (`config/custom_components/llm_cached_conversation_agent/`).
- The cache is written atomically; malformed files are handled gracefully.
