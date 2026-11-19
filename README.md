# HAI — A Completely Different Approach to AI

HAI is a storage engine for meaning built the way a language is built:
**words defined by words**. A fixed kernel of 850 prime words is grounded
by pointing at the world (pictures, sounds, acts — not other words), and
every word after that is defined *using only words already in the store*.
The store therefore grows like a city, not like a spreadsheet: new
buildings are always made from the old bricks.

The design comes from a student notebook from Nyambaria School (Kenya) —
a hand-written AI system design with a self-invented storage engine, prime
definitions, sub-database retrieval, and a fixed-core philosophy ("the
toolbelt, not the brain"). This repository is that notebook, refurbished
into something a compiler can check.

## The word network

* **Ring 0 — the primes.** The 850 words of Ogden's Basic English (1930,
  public domain): 100 operations, 400 general things, 200 picturable
  things, 100 general qualities, 50 opposite qualities. Each carries a
  short *grounding gloss* (what to point at, what to show the eye or ear).
  They are never defined by other words. Word numbers 1–850.
* **Ring 1 — the first expansion.** 326 words outside the kernel
  (everyday speech, computing, and the notebook's own concepts:
  `hello`, `computer`, `embedding`, `grounding`, `toolbelt`, `kernel`,
  `immutable`, `lifecycle`, `deterministic`…) each defined *strictly from
  ring-0 wordforms*. Word numbers 851–1176.
* **The rule that makes it a system:** a definition may only stand on
  words below it. `validator.py` enforces this mechanically — every
  definition token must be a seed word, a Basic English free form
  (pronouns, compounds, numerals — see `seed/whitelist.json`), or a
  regular word-form of a seed (`-s`, `-ed`, `-ing`, `-er`, `-est`).
  It runs clean: **850 + 326 words, zero violations.**

Word numbers are the notebook's "words as numbers" idea made real:
`hello` is word **#851** — the notebook's famous "3212 = hello" example,
at the position it actually occupies in this store.

```
seed/
  seed.json        850 primes: id, word, pos, ring, cat, gloss
  ring1.json      326 words:  id, word, pos, ring, def, uses[]
  whitelist.json  Basic English free forms (official compound list,
                   pronouns, numerals) — the legal machinery of definitions
  validator.py    enforces the ring rule; exits 0 when clean
  SOURCES.md      word-list provenance and cross-checks

core/
  lifecycle.adg   the fixed core, as an Ampersand graph (see below)

viz/
  network.adg     all 1176 words + 3000 definition edges as one .adg

toolbelt/
  embed.py        vector-store builder (Ollama nomic-embed-text, or a
                   deterministic offline hash backend)
  lookup.py       sub-database retrieval CLI

patches/
  ampersand_call_op.patch   verified 4-hunk diff adding a `call` op
                             (file bridge) to the Ampersand compiler
```

## Quickstart

```bash
# 1. check the network's integrity
cd seed && python3 validator.py

# 2. watch the fixed core walk all 1176 words and end itself
cd ../core
ampersand compile lifecycle.adg        # Ampersand v0.7 (github.com/jasonkerama-dev/Ampersand)
#  -> "[cycle 1176] word=1176 ... end node 'end' fired"

# 3. see the network
#    open viz/network.adg in the Ampersand web IDE canvas:
#    node w851 = "hello"; its edges are the primes it stands on

# 4. run retrieval
cd ../toolbelt
python3 embed.py                       # builds hai.db (offline backend)
python3 lookup.py "a machine with an electric brain"
#  -> #949 computer ...
python3 lookup.py round --cat things_picturable
python3 lookup.py --def hello
```

## The fixed core: why Ampersand

The notebook's Part H/I demanded a core that never updates itself, boots
offline, and forgets between cycles. Ampersand (by Jason Kerama) is
exactly that shape: a deterministic dataflow graph with WORM immutables,
seven enforced memory laws, a single pre-reserved arena, variables reset
every cycle, and a lifecycle that must end via an end node.

`core/lifecycle.adg` is the HAI core in that language:

* the **WORM boot manifest** (immutables: 850 seeds, 326 ring-1 words,
  total 1176, LAW 2) is written once at power-on and locked for life;
* the pipeline is the notebook's five stages — `entry → validate →
  score → route → end`;
* it walks word #1 to word #1176, one word per cycle, and terminates
  itself at exactly the manifest count (LAW 6, no endless loop);
* no strings, no vectors, no network inside the core: **the toolbelt, not
  the brain.** Everything that learns lives outside and is swapped freely.

`patches/ampersand_call_op.patch` adds a `call` op to the Ampersand
compiler (~46 lines, 4 hunks) so a graph node can pull one number from
the toolbelt through a *file bridge* (`$HAI_BRIDGE/<node>.in`) — still
deterministic, still offline, no network calls in the core. The patch was
applied, compiled and tested against Ampersand v0.7 before being filed
here; the demo run is in the patch header comment.

## Provenance

* **Word list:** Ogden's Basic English 850, category structure from
  ogden.basic-english.org as parsed by the BSD-3 `avoidwork/ogden`
  library, cross-checked against an independent copy — details in
  `seed/SOURCES.md`. Public domain (1930).
* **Grounding glosses and ring-1 definitions:** authored for HAI
  (this repository's own work).
* **Ampersand:** v0.7 by Jason Kerama (Apache-2.0), unmodified except for
  the optional, separately-filed patch above.
* **The original notebook:** hand-written system design notes from
  Nyambaria School.

## Roadmap

1. more ring-1 batches (the target is ~850+ words; `validator.py` makes
   each batch cheap to check),
2. Ollama `nomic-embed-text` vectors for real semantic retrieval
   (already wired — install Ollama and the hash backend steps aside),
3. ring 2 (words defined from rings 0+1; cycles begin — this is where
   Sigma.js takes over from the .adg canvas),
4. multimodal grounding for ring 0 (CLIP-style: picture ↔ word),
5. upstream the `call` op or keep the patch as HAI's own fork point.

## License

MIT (see LICENSE). The Basic English 850 word list is public domain;
Ampersand is Apache-2.0 and is not redistributed in this repository.
