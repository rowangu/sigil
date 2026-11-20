#!/usr/bin/env python3
"""SIGIL seed/ring1/ring2 validator.

Enforces the core invariant of the SIGIL storage engine:

  Ring 0  (primes)  : 850 Ogden Basic English words, grounded by glosses,
                      never defined by other words.
  Ring 1  (words)   : every word is defined USING ONLY ring-0 wordforms
                      (plus Basic English's official free machinery:
                      pronoun forms, compounds, numerals, and the regular
                      word-form rules -s/-es/-ed/-ing/-er/-est).
  Ring 2  (words)   : every word is defined using ONLY ring-0 + ring-1
                      wordforms (same free machinery). Never another ring-2
                      word — that would close a cycle, and the store is a
                      city built from older bricks only.

Usage:
    python3 validator.py            # validate seed.json + ring1.json + ring2.json
    python3 validator.py --ring 2    # seed + ring1 only (pre-ring-2 state)
    python3 validator.py --explain WORD   # show how a token resolves

Exit code 0 = clean; 1 = violations printed.
"""
import argparse
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
SEED = HERE / 'seed.json'
RING1 = HERE / 'ring1.json'
RING2 = HERE / 'ring2.json'
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


def resolve(token, base_forms, wl_forms):
    """Return the base word a token derives from, or None.

    base_forms: the CLOSED vocabulary the definition may draw on
    (ring-0 forms for ring-1 defs; ring-0+ring-1 for ring-2 defs).
    """
    if token in base_forms:
        return ('base', token)
    if token in wl_forms:
        return ('whitelist', token)
    # copied -> copy, studied -> study (irregular -ied)
    if token.endswith('ied') and token[:-3] + 'y' in base_forms:
        return ('base', token[:-3] + 'y')
    for suf in SUFFIXES:
        if not token.endswith(suf) or len(token) <= len(suf) + 1:
            continue
        stem = token[:-len(suf)]
        # flies -> fly, copies -> copy
        if suf == 'ies' and stem + 'y' in base_forms:
            return ('base', stem + 'y')
        if stem in base_forms:
            return ('base', stem)
        # making -> make, writing -> write
        if stem + 'e' in base_forms:
            return ('base', stem + 'e')
        # getting -> get, stopped -> stop (doubled consonant)
        if len(stem) > 1 and stem[-1] == stem[-2]:
            if stem[:-1] in base_forms:
                return ('base', stem[:-1])
            if stem[:-1] + 'e' in base_forms:
                return ('base', stem[:-1] + 'e')
    return None


def uses_from_def(def_text, base_forms, wl_forms):
    """Which base words a definition actually stands on."""
    used = {}
    for t in tokens(def_text):
        r = resolve(t, base_forms, wl_forms)
        if r and r[0] == 'base':
            used[r[1]] = used.get(r[1], 0) + 1
    return sorted(used.keys())


# ----------------------------------------------------------------- validation
def load():
    seed_doc = json.load(open(SEED, encoding='utf-8'))
    wl = json.load(open(WHITELIST, encoding='utf-8'))
    ring_doc = json.load(open(RING1, encoding='utf-8')) \
        if RING1.exists() else {'words': []}
    ring2_doc = json.load(open(RING2, encoding='utf-8')) \
        if RING2.exists() else {'words': []}
    return seed_doc, wl, ring_doc, ring2_doc


def validate(with_ring2=True):
    seed_doc, wl, ring_doc, ring2_doc = load()
    if not with_ring2:
        ring2_doc = {'words': []}
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

    # --- ring 2 checks ---------------------------------------------------
    # ring-2 words are defined from ring-0 + ring-1 forms ONLY
    base2_forms = set(seed_forms) | set(ring_forms)
    r2_forms = {}
    for e in ring2_doc.get('words', []):
        w = e['word'].lower()
        if w in base2_forms:
            errs.append(f'ring2 word overlaps lower ring: {w}')
        if w in r2_forms:
            errs.append(f'ring2 wordform duplicated: {w}')
        r2_forms[w] = e
        for t in tokens(e.get('def', '')):
            r = resolve(t, base2_forms, wl_forms)
            if r is None:
                errs.append(f"ring2 '{e['word']}': def token '{t}' "
                            f'is not lower-ring/whitelist/derivable')
    r2_ids = [e['id'] for e in ring2_doc.get('words', [])]
    next_id = 851 + len(ring_doc.get('words', []))
    if r2_ids and r2_ids != list(range(next_id, next_id + len(r2_ids))):
        errs.append(f'ring2 ids are not sequential from {next_id}')

    # --- report ----------------------------------------------------------
    print(f'ring0: {len(primes)} primes | counts: {counts}')
    print(f'ring1: {len(ring_doc.get("words", []))} words '
          f'(ids {ids[0] if ids else "-"}..{ids[-1] if ids else "-"})')
    if r2_ids:
        print(f'ring2: {len(r2_ids)} words '
              f'(ids {r2_ids[0]}..{r2_ids[-1]})')
    for w in warns:
        print('WARN:', w)
    if errs:
        print(f'\n{len(errs)} VIOLATION(S):')
        for e in errs[:60]:
            print('  *', e)
        return 1
    if r2_ids:
        print('\nCLEAN: ring 1 stands on the seed ring; '
              'ring 2 stands on rings 0 and 1.')
    else:
        print('\nCLEAN: all definitions stand on the seed ring alone.')
    return 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--ring', type=int, default=2,
                    help='highest ring to validate (1 or 2, default 2)')
    ap.add_argument('--explain', metavar='WORD')
    args = ap.parse_args()
    if args.explain:
        seed_doc, wl, _, _ = load()
        forms = {e['word'].lower() for e in seed_doc['primes']}
        ring_doc = json.load(open(RING1, encoding='utf-8')) \
            if RING1.exists() else {'words': []}
        forms |= {e['word'].lower() for e in ring_doc['words']}
        wl_forms = {w.lower() for v in wl.values() for w in v}
        print(resolve(args.explain.lower(), forms, wl_forms))
    else:
        sys.exit(validate(with_ring2=args.ring >= 2))
