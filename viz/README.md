# viz/ — seeing the network

`network.adg` is the whole word store as a single Ampersand graph:

* every word is a WORM immutable node: `w851 { value: "851:hello" }`;
* every ring-1 definition draws edges from the primes it stands on
  (`edge w74 -> w851;` — `hello` is built from word #74, `say`, among
  others);
* direction is `seed -> word` (data flows from primes into definitions),
  which keeps the graph a DAG: ring 1 only ever references ring 0.

1176 nodes, 3000 edges, one file that compiles clean under Ampersand
v0.7 (`ampersand compile network.adg --json`).

Open it in the Ampersand web IDE (infinite canvas) and the word network
is right there: click `w851` ("hello") and follow its edges down into
the 850.

Ring 2 and beyond will contain cycles (a ring-2 word may be used by
another ring-2 word's definition in a later batch) — at that point the
`.adg` canvas stops being the right tool and Sigma.js / Cytoscape take
over. Until then, the DAG fits the canvas exactly.

Regenerate after editing `seed.json` / `ring1.json`:

```bash
python3 scripts/gen_network_adg.py    # (lives in the build scripts;
                                       # output is committed, so the
                                       # canvas works without rebuilding)
```
