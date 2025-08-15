# Changelog (Italiano)

## 1.2 2025/08/15
Novità introdotte:
- System prompt (opzionale) inviato a Ollama (campo `system` nell'API generate)
- Controlli di campionamento per Ollama in `options`:
  - `top_p` (nucleus sampling, default 0.9)
  - `top_k` (default 40)
  - `repeat_penalty` (default 1.1)
  - `min_p` (default 0.0)
  - `seed` (default -1 = casuale)
- Aggiornate UI e traduzioni (IT/EN) per i nuovi campi
- Documentazione aggiornata in `configuration.md`

## 1.1 2025/08/15
Aggiunte e cambiamenti:
- Opzione `match_punctuation` per il confronto in cache:
  - Se `true` (default), la ricerca richiede corrispondenza esatta della punteggiatura
  - Se `false`, la punteggiatura viene ignorata; vengono registrati alias delle forme alternative
- Gestione robusta del cambio di `match_punctuation`:
  - Merge sicura tra file cache variante `_true`/`_false` per non perdere voci
  - Lettura/validazione dei file variante prima del reload
  - Scritture atomiche e lock I/O per evitare race condition

## 1.0 2025/08/15
Funzionalità iniziali (tutto tranne `match_punctuation`):
- Agente conversazionale per Home Assistant (Compatibile con Assist)
- Cache locale su file JSON con risposta immediata se presente
- Fallback automatico a Ollama quando la risposta non è in cache
- Scrittura atomica del file cache e lettura tollerante a file parzialmente troncati
- Configurazione dalla UI (Config Flow) e modifica post-configurazione (Options Flow) applicata a caldo
- Percorso DB configurabile (default `qa_cache.json` nella cartella dell’integrazione)
- Lingue conversazione supportate: tutte (`supported_languages = "*"`)
- Traduzioni UI disponibili (IT, EN, DE, EL, ES, FR, PL, PT)
