# Word-list provenance

The 850-word kernel of SIGIL is Ogden's Basic English (C. K. Ogden, 1930,
public domain). Because the canonical ogden.basic-english.org site is
dead-domain, the list was assembled from two independent copies and
cross-checked:

1. **avoidwork/ogden** (BSD-3-Clause, Jason Mulligan, 2016) —
   `github.com/avoidwork/ogden`, file `lib/ogden.js`, category arrays
   `operations`, `thingsGeneral`, `thingsPicturable`, `qualitiesGeneral`,
   `qualitiesOpposites`. Used as the master (it is a maintained parse of
   the official list).
2. **An independent copy** of the ogden.basic-english.org word lists
   (same category split, taken from a third-party study repository).

Agreement between the two copies: category-perfect for all 550
things/qualities words; the operations list (100 words) matches
word-for-word; `plough`/`plow` is one slot with a spelling variant
(`plow`), as is `grey`/`gray` — the official list's convention. Both
sources agree on the famous quirks: `what` and `which` are **not** in the
850 (Basic derives them), and `she`, `it`, `we`, `they` are treated as
free pronoun machinery rather than counted vocabulary.

The whitelist (`whitelist.json`) follows the same provenance: its
`compound_basic` tier (209 entries) is the official Ogden compound-words
list (also from avoidwork/ogden), `pronouns` is the official free
pronoun set, and `numerals`/`grammar` are the small closed sets the
definitions' own metalanguage needs (`more`, `most`, `better`, `best`,
`worse`, `worst`, `an` — the article form of the seed `a`).

Counts in `seed.json` (which `validator.py` re-checks):

| category              | words |
| --------------------- | ----- |
| operations            |   100 |
| things_general        |   400 |
| things_picturable     |   200 |
| qualities_general     |   100 |
| qualities_opposites   |    50 |
| **total primes**      | **850**|

The 850 grounding glosses and all 326 ring-1 definitions are original
work authored for this repository.

## Ring 2 (word selection)

Ring-2 words are frequency-ranked English word-forms taken in order from
the **google-10000-english 20k list** (first20hours/google-10000-english,
MIT licence) — the 20,000 most common word-forms of American English
in Google's trillion-word corpus (originally compiled by Google's
research team as the Google Web 1T 5-gram top-10k/100k lists).

Selection rules (see `tools/ring2/build_candidates.py`, kept with
the generator, not in this repo):

* every list entry already present in ring 0, ring 1, or the whitelist
  is skipped (the store never defines a word twice);
* obvious non-words (numbers, URLs, 1–2 letter noise) are dropped;
* a small profanity filter removes a handful of vulgar terms (this is a
  school-born project);
* ids continue from 1177, so word order = frequency order.

The 1449 ring-2 *definitions* are original work authored for this
repository under a closed-vocabulary contract: each definition was
written to use only ring-0 + ring-1 wordforms (plus the free machinery
and regular endings), then checked mechanically — every token must
resolve to a lower-ring wordform in `validator.py`. Definitions that
failed were dropped or rewritten; only validated ones are in
`ring2.json` (0 violations). Batch 1 is checkpointed and later batches
extend it in frequency order.
