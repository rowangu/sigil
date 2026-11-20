# toolbelt/ — the learning side

Everything that can change, learn, or be replaced lives here. The core
(`core/`) only walks and decides; this folder does the heavy lifting and
may be rewritten any day without touching the core.

## embed.py

Reads `seed/seed.json` + `seed/ring1.json`, embeds every word with its
definition text, and writes `hai.db` (SQLite; 1176 rows, one vector per
word).

Backends, first available wins:

1. **ollama** — `nomic-embed-text` at `localhost:11434`
   (`ollama pull nomic-embed-text`). Real semantic vectors.
2. **hash** — deterministic 256-dim char-trigram embedding. Bit-exact on
   every machine, zero dependencies, surprisingly usable for retrieval
   demos. This is the default fallback when Ollama is absent.

```bash
python3 embed.py                 # auto: ollama if present, else hash
python3 embed.py --backend hash # force offline
```

## lookup.py

Sub-database retrieval — the notebook's idea: query the store, get back
word numbers and their definitions, optionally restricted to one
sub-database (a ring-0 category or the whole ring 1).

```bash
python3 lookup.py hello                      # exact record (#851)
python3 lookup.py --def computer             # full record + definition
python3 lookup.py "a machine with an electric brain"   # -> computer
python3 lookup.py round --cat things_picturable         # -> ball, moon, orange
python3 lookup.py "keeping things for later" --ring 1  # -> storage
```

Cosine similarity over the exact vector store — fine at 1176 words;
ann indexes (FAISS / sqlite-vec) are the natural next step at ring 2
scale.
