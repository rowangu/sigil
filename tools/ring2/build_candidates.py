#!/usr/bin/env python3
"""Build the ring-2 candidate list for SIGIL.

Source: google-10000-english 20k frequency list (public domain-ish list of
most common English word-forms). We take words NOT already in the store
(850 primes + 326 ring-1 + whitelist machinery), filter junk/profanity,
keep frequency order, and assign ids from 1177.

Output: tools/ring2/candidates.jsonl (next to this script)
        one {"id":N,"word":W,"rank":R} per line
"""
import json
import pathlib
import re

HAI = pathlib.Path(__file__).resolve().parent.parent.parent
SRC = pathlib.Path(__file__).resolve().parent / 'google20k.txt'
OUT = HERE / 'candidates.jsonl'
TARGET = 10800   # buffer above the 10,000 the user asked for

seed = json.load(open(HAI / 'seed' / 'seed.json', encoding='utf-8'))
ring1 = json.load(open(HAI / 'seed' / 'ring1.json', encoding='utf-8'))
wl = json.load(open(HAI / 'seed' / 'whitelist.json', encoding='utf-8'))

known = set()
for e in seed['primes']:
    known.add(e['word'].lower())
    for v in e.get('variants', []):
        known.add(v.lower())
for e in ring1['words']:
    known.add(e['word'].lower())
for tier, items in wl.items():
    known |= {w.lower() for w in items}

# crude profanity filter (public repo, school project)
BAD = set('''fuck shit piss cock dick cunt bitch asshole bastard prick
whore slut nigger nigga fag faggot retard rape raping porn porno cumshot
blowjob handjob wank jerkoff jizz cumming damn goddammit crap
nazi gestapo heil kike spic wetback towelhead''' .split())

TOKEN_RE = re.compile(r'^[a-z]+$')

cands, seen = [], set()
for rank, raw in enumerate(SRC.read_text(encoding='utf-8').split('\n'), 1):
    w = raw.strip().lower()
    if not w:
        continue
    if not TOKEN_RE.match(w):
        continue                    # numbers, urls, mixed junk
    if len(w) < 3 and w not in ('oil', 'ox', 'eye', 'ear', 'egg', 'arm',
                                'leg', 'toe', 'lip', 'hip', 'rib', 'ink',
                                'jam', 'ivy'):
        if len(w) <= 2:
            continue                # 1-2 letter noise (ab, aa, om ...)
    if w in known:
        continue
    if any(bad in w or w == bad for bad in BAD if len(bad) >= 4):
        if w in BAD:
            continue
        if any(re.search(rf'\b{bad}\b', w) for bad in BAD if len(bad) >= 4):
            continue
    if w in seen:
        continue
    seen.add(w)
    cands.append(w)
    if len(cands) >= TARGET:
        break

OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, 'w', encoding='utf-8') as f:
    for i, w in enumerate(cands):
        f.write(json.dumps({'id': 1177 + i, 'word': w}) + '\n')

print(f'candidates: {len(cands)} (ids 1177..{1176 + len(cands)})')
print('first 15:', cands[:15])
print('last 5:', cands[-5:])
print(f'wrote {OUT}')
