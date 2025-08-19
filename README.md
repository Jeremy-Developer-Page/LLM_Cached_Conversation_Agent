<p align="center">
  <img src="assets/logo.png" alt="LLM Cached Conversation Agent logo" width="128" height="128" />
</p>

# LLM Cached Conversation Agent (Home Assistant)
Italiano | [English](README.en.md) | [Changelog](CHANGELOG.md) | [Changelog EN](CHANGELOG.en.md)

Un agente conversazionale per Home Assistant con cache locale su file e fallback LLM (Ollama) per risposte non presenti in cache.

- Struttura finale in Home Assistant (sotto `config/`):

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
      qa_cache.json  # (opzionale; creato automaticamente al primo uso se mancante)
```

- Percorso di destinazione: `config/custom_components/llm_cached_conversation_agent/`
- Copia via Samba (SMB):
  - Windows: `\\homeassistant\config` oppure `\\<IP_HA>\config`
  - macOS: `smb://homeassistant.local/config` oppure `smb://<IP_HA>/config`
  - Linux: `smb://homeassistant.local/config` oppure `smb://<IP_HA>/config`

Dettagli e istruzioni complete nella sezione “2) Installazione…”.


Un agente conversazionale per Home Assistant con cache locale su file e fallback LLM (Ollama) per risposte non presenti in cache.

## 1) Requisiti hardware e software

- Home Assistant (Core, OS o Supervised) già in esecuzione
- Aggiunta “Samba share” disponibile (per copia file via rete) oppure altro metodo equivalente per accedere alla cartella `config/`
- Ollama in esecuzione e raggiungibile da Home Assistant (default: http://127.0.0.1:11434)
- Risorse consigliate per il modello:
  - CPU x86_64/ARMv8 recente oppure Raspberry Pi 4/5
  - RAM: dipende dal modello scelto (es: 8 GB raccomandati per modelli medi)
  - Spazio disco sufficiente per i modelli Ollama e per il file cache
- Nessuna dipendenza Python extra (il manifest non richiede pacchetti aggiuntivi)

## 2) Installazione su Home Assistant (via Samba: Windows/macOS/Linux)

### 2.1 Abilitare l’accesso Samba
- In HA: Impostazioni → Componenti aggiuntivi → Store → installa “Samba share” → configura (utente/password) → avvia.
- Dopo l’avvio, la cartella `config/` di HA sarà accessibile via rete (SMB).

### 2.2 Copiare i file nella cartella dell’integrazione
- Percorso di destinazione in HA: `config/custom_components/llm_cached_conversation_agent/`
- Copia l’intera cartella `custom_components/llm_cached_conversation_agent` del progetto in quel percorso.

Suggerimenti per OS:
- Windows: in Esplora File apri `\\homeassistant\config` (oppure `\\<IP_HA>\config`), vai in `custom_components/`, crea `llm_cached_conversation_agent` e incolla i file.
- macOS: Finder → Vai → Connessione al server… → `smb://homeassistant.local/config` (oppure `smb://<IP_HA>/config`) → `custom_components/` → `llm_cached_conversation_agent` → incolla i file.
- Linux: nel file manager: `smb://homeassistant.local/config` (oppure `smb://<IP_HA>/config`), poi come sopra.

### 2.3 Riavviare Home Assistant
- Impostazioni → Sistema → Riavvia (o solo Core) per caricare l’integrazione.

### 2.4 Aggiungere l’integrazione dalla UI
- Impostazioni → Dispositivi e servizi → Aggiungi integrazione → cerca “LLM Cached Conversation Agent”.
- Compila i campi:
  - Base URL di Ollama (es. `http://127.0.0.1:11434` o host del container `http://ollama:11434`)
  - Modello (es. `llama3`)
  - Nome file DB (default `qa_cache.json`)

### 2.5 (Opzionale) Selezionare l’agente in Assist
- Impostazioni → Assist → Imposta “LLM Cached Conversation Agent” come agente predefinito per la/e lingua/e desiderata/e.

## 3) Funzioni e lingue supportate

Funzioni principali:
- Cache locale su file JSON; risposte immediate se già presenti
- Fallback automatico a Ollama quando non trova la risposta in cache
- Scrittura atomica del file cache e lettura tollerante a file parzialmente troncati
- Configurazione dalla UI (Config Flow)
- Modifica post-configurazione dalla UI (Options Flow) con applicazione a caldo
- Conversation Agent registrato in Home Assistant (compatibile con Assist)
- Percorso DB configurabile (di default `qa_cache.json` nella cartella dell’integrazione)
 - System prompt opzionale (inviato come `system` all'API generate di Ollama)
 - Opzioni sampling (Ollama, in `options`): `top_p`, `top_k`, `repeat_penalty`, `min_p`, `seed`
 - Toggle `include_datetime`: aggiunge data/ora correnti (fuso di HA) al system prompt

Lingue supportate:
- Conversazione/Assist: tutte le lingue (l’agente dichiara `*` come `supported_languages`)
- Traduzioni UI dell’integrazione: IT, EN, DE, EL, ES, FR, PL, PT

## 4) Come utilizzarlo

- Fai una domanda tramite Assist.
- Se la domanda (normalizzata) è presente in cache, la risposta è immediata.
- Se non è in cache, l’agente interroga l’LLM tramite Ollama con il modello configurato, salva la risposta nel DB e te la restituisce.
- Per modificare la configurazione dopo l’installazione: Impostazioni → Dispositivi e servizi → Integrazioni → “LLM Cached Conversation Agent” → Configura. Le modifiche (Base URL, Modello, Nome file DB) sono applicate al volo.

Modifica manuale del DB (opzionale):
- Percorso predefinito: `config/custom_components/llm_cached_conversation_agent/qa_cache.json` (puoi cambiarlo dalle opzioni).
- Struttura file:
  - `version`: versione del formato
  - `items`: lista di oggetti `{ q, q_norm, a, ts }`
  - `q_norm` è la chiave di ricerca (testo normalizzato a minuscolo con spazi ripuliti).

  Opzione importante:
  - `match_punctuation` (booleano, default: true): se impostato a true, la ricerca richiede che la punteggiatura nella domanda corrisponda esattamente al valore memorizzato in `q_norm`; se impostato a false, il confronto ignora la punteggiatura. Nota: il file JSON mantiene sempre la punteggiatura in `q_norm` quando una domanda viene salvata — l'opzione influenza solo il comportamento del confronto al lookup.

  Parametri LLM (Ollama):
  - `system_prompt` (stringa, opzionale): istruzione di sistema per guidare lo stile/il contesto del modello
  - `include_datetime` (booleano): se true, aggiunge data/ora correnti (timezone di HA) al system prompt
  - `top_p` (float): nucleus sampling (default 0.9)
  - `top_k` (int): limita la scelta ai top-k token (default 40)
  - `repeat_penalty` (float): penalità per ridurre ripetizioni (default 1.1)
  - `min_p` (float): soglia di probabilità minima (default 0.0)
  - `seed` (int): seed casuale (-1 = random)

  Comportamento al cambio dell'opzione:
  - Quando viene modificato `match_punctuation`, l'integrazione ora effettua una merge sicura delle voci dal file cache precedentemente attivo nel file variante che diventerà attivo (es. `qa_cache_true.json` ↔ `qa_cache_false.json`) in modo da non perdere voci esistenti.
  - La merge e la ricarica vengono eseguite sotto un lock I/O interno e entrambi i file variante vengono letti/validati prima della ricarica. Questo evita scritture concorrenti o condizioni di race che potrebbero corrompere o sovrascrivere il file attivo.
  - Le scritture su disco restano atomiche e ora il codice garantisce che il payload venga scritto esattamente sul file attivo calcolato al momento del salvataggio, evitando sovrascritture accidentali durante cambi di configurazione concorrenti.

Note utili:
- Se Ollama è su un altro host/container, aggiorna il Base URL di conseguenza e verifica la raggiungibilità di rete.
- Per un reset rapido della cache, spegni HA, rimuovi `qa_cache.json`, riaccendi: verrà rigenerato.
- Log: Impostazioni → Sistema → Registri (cerca `custom_components.llm_cached_conversation_agent`).

## 5) To‑Do (future aggiunte)

- Integrazione API OpenAI

---

License: GPL-3.0