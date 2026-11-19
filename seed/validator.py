#!/usr/bin/env python3
"""HAI seed/ring1 validator.

Enforces the core invariant of the HAI storage engine:

  Ring 0  (primes)  : 850 Ogden Basic English words, grounded by glosses,
                      never defined by other words.
  Ring 1  (words)   : every word is defined USING ONLY ring-0 wordforms
                      (plus Basic English's official free machinery:
                      pronoun forms, compounds, numerals, and the regular
                      word-form rules -s/-es/-ed/-ing/-er/-est).

Usage:
    python3 validator.py            # validate seed.json + ring1.json
    python3 validator.py --explain WORD   # show how a token resolves

Exit code 0 = clean; 1 = violations printed.
"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
SEED = HERE / 'seed.json'
RING1 = HERE / 'ring1.json'
WHITELIST = HERE / 'whitelist.json'

# ----------------------------------------------------------------- tokenizing
TOKEN_RE = re.compile(r"[a-z]+(?:'[a-z]+)?")


def tokens(text: str):
    out = []
    for raw in TOKEN_RE.findall(text.lower()):
        if raw.endswith("'s"):
            raw = raw[:-2]
        out.append(raw)
    return out


# ----------------------------------------------------------------- morphology
SUFFIXES = ('es', 's', 'ed', 'd', 'ing', 'er', 'est', 'ies')


def resolve(token, seed_forms, wl_forms):
    """Return the base word a token derives from, or None."""
    if token in seed_forms:
        return ('seed', token)
    if token in wl_forms:
        return ('whitelist', token)
    for suf in SUFFIXES:
        if not token.endswith(suf) or len(token) <= len(suf) + 1:
            continue
        stem = token[:-len(suf)]
        # flies -> fly, copies -> copy
        if suf == 'ies' and stem + 'y' in seed_forms:
            return ('seed', stem + 'y')
        if stem in seed_forms:
            return ('seed', stem)
        # making -> make, writing -> write
        if stem + 'e' in seed_forms:
            return ('seed', stem + 'e')
        # getting -> get, stopped -> stop (doubled consonant)
        if len(stem) > 1 and stem[-1] == stem[-2]:
            if stem[:-1] in seed_forms:
                return ('seed', stem[:-1])
            if stem[:-1] + 'e' in seed_forms:
                return ('seed', stem[:-1] + 'e')
    return None


def uses_from_def(def_text, seed_forms, wl_forms):
    """Which seed words a definition actually stands on."""
    used = {}
    for t in tokens(def_text):
        r = resolve(t, seed_forms, wl_forms)
        if r and r[0] == 'seed':
            used[r[1]] = used.get(r[1], 0) + 1
    return sorted(used.keys())


# ----------------------------------------------------------------- validation
def load():
    seed_doc = json.load(open(SEED, encoding='utf-8'))
    wl = json.load(open(WHITELIST, encoding='utf-8'))
    ring_doc = json.load(open(RING1, encoding='utf-8')) \
        if RING1.exists() else {'words': []}
    return seed_doc, wl, ring_doc


def validate():
    seed_doc, wl, ring_doc = json.load(open(SEED, encoding='utf-8')), \
        json.load(open(WHITELIST, encoding='utf-8')), \
        (json.load(open(RING1, encoding='utf-8'))
         if RING1.exists() else {'words': []})
    primes = seed_doc['primes']
    errs, warns = [], []

    # --- ring 0 checks ---------------------------------------------------
    counts = {}
    seed_forms = set()
    for i, e in enumerate(primes, 1):
        if e['id'] != i:
            errs.append(f'seed id gap: pos {i} has id {e["id"]}')
        if not e.get('gloss'):
            errs.append(f'seed #{e["id"]} ({e["word"]}) has empty gloss')
        w = e['word'].lower()
        if w in seed_forms:
            errs.append(f'seed wordform duplicated: {w}')
        seed_forms.add(w)
        for v in e.get('variants', []):
            if v.lower() in seed_forms:
                errs.append(f'variant collides: {v}')
            seed_forms.add(v.lower())
        counts[e['cat']] = counts.get(e['cat'], 0) + 1
    if len(primes) != 850:
        errs.append(f'expected 850 primes, found {len(primes)}')
    expect = {'operations': 100, 'things_general': 400,
              'things_picturable': 200, 'qualities_general': 100,
              'qualities_opposites': 50}
    for cat, n in expect.items():
        if counts.get(cat) != n:
            errs.append(f'category {cat}: {counts.get(cat)} != {n}')

    wl_forms = set()
    for tier, items in wl.items():
        wl_forms |= {w.lower() for w in items}

    # --- ring 1 checks ---------------------------------------------------
    ring_forms = {}
    for e in ring_doc.get('words', []):
        w = e['word'].lower()
        if w in seed_forms:
            errs.append(f'ring1 word overlaps seed: {w}')
        if w in ring_forms:
            errs.append(f'ring1 wordform duplicated: {w}')
        ring_forms[w] = e
        for t in tokens(e.get('def', '')):
            r = resolve(t, seed_forms, wl_forms)
            if r is None:
                errs.append(f"ring1 '{e['word']}': def token '{t}' "
                            f'is not seed/whitelist/derivable')
    ids = [e['id'] for e in ring_doc.get('words', [])]
    if ids and ids != list(range(851, 851 + len(ids))):
        errs.append('ring1 ids are not sequential from 851')

    # --- report ----------------------------------------------------------
    print(f'ring0: {len(primes)} primes | counts: {counts}')
    print(f'ring1: {len(ring_doc.get("words", []))} words '
          f'(ids {ids[0] if ids else "-"}..{ids[-1] if ids else "-"})')
    for w in warns:
        print('WARN:', w)
    if errs:
        print(f'\n{len(errs)} VIOLATION(S):')
        for e in errs[:60]:
            print('  *', e)
        return 1
    print('\nCLEAN: all definitions stand on the seed ring alone.')
    return 0


if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '--explain':
        seed_doc, wl, _ = load()
        seed_forms = {e['word'].lower() for e in seed_doc['primes']}
        wl_forms = {w.lower() for v in wl.values() for w in v}
        print(resolve(sys.argv[2].lower(), seed_forms, wl_forms))
    else:
        sys.exit(validate())
