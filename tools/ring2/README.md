# ring-2 generator — grows the store with new words

Ring 2 is the store's growing edge: ordinary English words, each defined
strictly from ring-0 + ring-1 wordforms, never from another ring-2 word
(the validator forbids it; a cycle would close).

`seed/ring2.json` in this repo is **batch 1** (1449 words, ids
1177–2625, frequency-ranked). The generator is checkpointed: run it
again any time and it resumes where it stopped.

## Pipeline

```
build_candidates.py   20k frequency list -> candidates.jsonl
                      (skips words already in the store, drops junk)
gen_ring2.py          candidates -> done.jsonl
                      (LLM writes each definition under a closed-
                      vocabulary contract; every token is then resolved
                      mechanically with seed/validator.py's own resolver;
                      failures are named and repaired, then recycled)
assemble.py           done.jsonl -> seed/ring2.json
                      (sequential ids from 1177, pos heuristic,
                      uses[] computed with the same resolver)
```

## Usage

```bash
cd tools/ring2
python3 build_candidates.py        # needs google20k.txt (see below)
timeout 580 python3 gen_ring2.py   # chunked run; re-run until COMPLETE
python3 assemble.py                # rebuild seed/ring2.json
cd ../../seed && python3 validator.py   # must print CLEAN, 0 violations
```

`gen_ring2.py` calls the `z-ai` CLI (`npm i -g z-ai-web-dev-sdk`) for
definition authoring and rate-limits itself (pace + 429 backoff);
runs are chunked (~9 min) because the API throttles sustained bursts.
Tuning: `RING2_BATCH`, `RING2_PACE`, `RING2_SECONDS` env vars.

The 20k frequency list lives at
`github.com/first20hours/google-10000-english` (file `20k.txt`, MIT).
Drop a copy next to this script as `google20k.txt`.

## After each batch

Re-run `assemble.py`, then from the repo root:

```bash
python3 scripts/gen_network_adg.py  (in the dev tree) or regenerate viz
python3 toolbelt/embed.py           # rebuild hai.db with the new words
python3 seed/validator.py           # the contract: 0 violations
```

and update `core/lifecycle.adg`'s manifest counts
(`ring2`, `total_words`, `max_cycles`) — the fixed core walks exactly
the manifest count and terminates (LAW 6).
