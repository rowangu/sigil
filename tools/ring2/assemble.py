#!/usr/bin/env python3
"""Assemble seed/ring2.json from ring2/done.jsonl.

- Sequential ids from 1177, in candidate (frequency) order.
- pos via first-token heuristic (noun default; 'to '->verb; 'in a'->adv;
  'one who'->noun; 'having/being'->adj).
- uses[] computed with validator's own resolver against ring-0+ring-1
  forms, so the docs network edges match the validator exactly.

Then the ring-2 words are re-validated through seed/validator.py itself
(by the caller).
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
HAI = pathlib.Path(__file__).resolve().parent.parent.parent / 'seed'
DONE = HERE / 'done.jsonl'
CAND = HERE / 'candidates.jsonl'
OUT = HAI / 'ring2.json'

sys.path.insert(0, str(HAI))
import validator  # noqa: E402

seed = json.load(open(HAI / 'seed.json', encoding='utf-8'))
ring1 = json.load(open(HAI / 'ring1.json', encoding='utf-8'))
wl = json.load(open(HAI / 'whitelist.json', encoding='utf-8'))

r0 = {e['word'].lower() for e in seed['primes']}
r1w = {e['word'].lower() for e in ring1['words']}
BASE = r0 | r1w
WL = {w.lower() for v in wl.values() for w in v}

done = {}
for line in DONE.read_text(encoding='utf-8').splitlines():
    if line.strip():
        rec = json.loads(line)
        done[rec['word']] = rec['def']

# frequency order of candidates defines the id order
order = [json.loads(l)['word'] for l in
         CAND.read_text(encoding='utf-8').splitlines() if l.strip()]

words = []
for i, w in enumerate([w for w in order if w in done]):
    d = done[w]
    toks = d.split()
    if d.startswith('to '):
        pos = 'verb'
    elif d.startswith('in a ') or d.endswith(' way'):
        pos = 'adv'
    elif toks[:2] == ['one', 'who'] or toks[:3] == ['the', 'act', 'of']:
        pos = 'noun'
    elif toks[:2] in (['having', 'a'], ['being', 'a'],
                      ['full', 'of'], ['not', 'able']):
        pos = 'adj'
    else:
        pos = 'noun'
    uses = validator.uses_from_def(d, BASE, WL)
    words.append({'id': 1177 + i, 'word': w, 'pos': pos, 'ring': 2,
                  'def': d, 'uses': uses})

doc = {
    'meta': {
        'ring': 2,
        'count': len(words),
        'source': ('frequency-ranked English word-forms (ranks 2..20000 of '
                   'the google-10000-english 20k list), minus everything '
                   'already in the store'),
        'method': ('each definition authored under a closed-vocabulary '
                   'contract and validated mechanically: every token must '
                   'resolve to a ring-0/ring-1 wordform, a Basic English '
                   'free form, or a regular word-form of one '
                   '(-s/-es/-ed/-d/-ing/-er/-est/-ied); see '
                   'seed/validator.py'),
        'status': ('checkpointed batch 1 of an ongoing expansion; the '
                   'generator resumes from done.jsonl'),
    },
    'words': words,
}

OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + '\n',
               encoding='utf-8')
n_uses = sum(len(e['uses']) for e in words)
print(f'ring2.json: {len(words)} words (ids 1177..{1176 + len(words)}), '
      f'{n_uses} use-edges, pos counts:')
from collections import Counter  # noqa: E402
print(' ', Counter(e['pos'] for e in words))
