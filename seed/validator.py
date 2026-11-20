#!/usr/bin/env python3
"""SIGIL multi-ring validator.

Enforces the core invariant of the SIGIL storage engine:

  Ring 0  (primes)  : 850 Ogden Basic English words, grounded by glosses,
                      never defined by other words.
  Ring N (N >= 1)   : every word is defined USING ONLY wordforms from
                      rings 0..N-1 (plus Basic English's official free
                      machinery: pronoun forms, compounds, numerals, and
                      the regular word-form rules -s/-es/-ed/-ing/-er/-est).

The store is a city built from older bricks only: a word in ring N can
never be defined by another word in the same ring or any outer ring.

Usage:
    python3 validator.py                 # validate all rings present
    python3 validator.py --ring 2        # validate up through ring 2
    python3 validator.py --explain WORD  # show how a token resolves
    python3 validator.py --max-ring 5    # validate up through ring 5

Exit code 0 = clean; 1 = violations printed.
"""
import argparse
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
SEED = HERE / 'seed.json'
WHITELIST = HERE / 'whitelist.json'
# Rings 1..N: ring1.json, ring2.json, ...
MAX_RING_FILES = 9

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
    (ring-0 forms for ring-1 defs; ring-0+ring-1 for ring-2 defs;
    rings 0..N-1 for ring-N defs).
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


# ----------------------------------------------------------------- loading
def load_rings(max_ring=None):
    """Load all rings present on disk up to max_ring (or all if None).

    Returns: (seed_doc, wl, [ring1_doc, ring2_doc, ...])
    """
    seed_doc = json.load(open(SEED, encoding='utf-8'))
    wl = json.load(open(WHITELIST, encoding='utf-8'))
    rings = []
    for n in range(1, MAX_RING_FILES + 1):
        if max_ring is not None and n > max_ring:
            break
        p = HERE / f'ring{n}.json'
        if not p.exists():
            break
        rings.append(json.load(open(p, encoding='utf-8')))
    return seed_doc, wl, rings


# ----------------------------------------------------------------- validation
def validate(max_ring=None):
    seed_doc, wl, rings = load_rings(max_ring)
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

    print(f'ring0: {len(primes)} primes | counts: {counts}')

    # --- ring 1..N checks -------------------------------------------------
    # Forms accumulated from lower rings; ring N's defs may use rings 0..N-1.
    lower_forms = set(seed_forms)
    next_id = 851
    for n, ring_doc in enumerate(rings, start=1):
        words = ring_doc.get('words', [])
        ring_forms = {}
        for e in words:
            w = e['word'].lower()
            if w in lower_forms:
                errs.append(f'ring{n} word overlaps lower ring: {w}')
            if w in ring_forms:
                errs.append(f'ring{n} wordform duplicated: {w}')
            ring_forms[w] = e
            for t in tokens(e.get('def', '')):
                r = resolve(t, lower_forms, wl_forms)
                if r is None:
                    errs.append(
                        f"ring{n} '{e['word']}': def token '{t}' "
                        f'is not lower-ring/whitelist/derivable')
        ids = [e['id'] for e in words]
        if ids and ids != list(range(next_id, next_id + len(ids))):
            errs.append(f'ring{n} ids are not sequential from {next_id}')
        if ids:
            print(f'ring{n}: {len(ids)} words '
                  f'(ids {ids[0]}..{ids[-1]})')
        # this ring becomes lower-ring for the next ring
        lower_forms |= set(ring_forms)
        next_id += len(words)

    # --- report ----------------------------------------------------------
    for w in warns:
        print('WARN:', w)
    if errs:
        print(f'\n{len(errs)} VIOLATION(S):')
        for e in errs[:60]:
            print('  *', e)
        if len(errs) > 60:
            print(f'  ... and {len(errs) - 60} more')
        return 1
    print(f'\nCLEAN: {len(rings)} ring(s) validated; '
          f'each ring stands only on lower rings.')
    return 0


def explain(word):
    """Show how a token resolves across all rings present."""
    seed_doc, wl, rings = load_rings()
    forms = {e['word'].lower() for e in seed_doc['primes']}
    for e in seed_doc['primes']:
        for v in e.get('variants', []):
            forms.add(v.lower())
    ring_of = {w: 0 for w in forms}
    for n, ring_doc in enumerate(rings, start=1):
        for e in ring_doc.get('words', []):
            forms.add(e['word'].lower())
            ring_of[e['word'].lower()] = n
    wl_forms = {w.lower() for v in wl.values() for w in v}
    r = resolve(word.lower(), forms, wl_forms)
    if r is None:
        print(f'{word!r}: UNRESOLVED (not in store, not whitelist, '
              f'no morphological derivation)')
    else:
        kind, base = r
        ring = ring_of.get(base, 'whitelist' if kind == 'whitelist' else '?')
        print(f'{word!r}: {kind} -> {base!r} (ring {ring})')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--ring', type=int, default=None,
                    help='(legacy alias for --max-ring) highest ring to validate')
    ap.add_argument('--max-ring', type=int, default=None,
                    help='highest ring to validate (default: all present)')
    ap.add_argument('--explain', metavar='WORD')
    args = ap.parse_args()
    if args.explain:
        explain(args.explain)
    else:
        max_ring = args.max_ring if args.max_ring is not None else args.ring
        sys.exit(validate(max_ring=max_ring))
