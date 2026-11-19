#!/usr/bin/env python3
"""HAI toolbelt — lookup.py: sub-database retrieval over the word network.

Give it a word or a question; it embeds the query with the same backend
embed.py used, scans the vector store, and returns the nearest words with
their word-numbers and definitions.

Sub-databases (--cat) are the notebook's sub-databases: the ring-0
categories (operations, things_general, things_picturable,
qualities_general, qualities_opposites) and ring1.

Examples:
    python3 lookup.py hello
    python3 lookup.py "a machine that thinks" --topk 5
    python3 lookup.py water --cat things_picturable
    python3 lookup.py "" --ring 1 --topk 20 --def computer
"""
import argparse
import json
import math
import pathlib
import re
import sqlite3
import struct
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from embed import embed_texts, DIMS  # noqa: E402

DB = HERE / 'hai.db'
SEED = HERE.parent / 'seed' / 'seed.json'
RING1 = HERE.parent / 'seed' / 'ring1.json'


def cosine(a, b):
    d = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return d / (na * nb)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('query', nargs='*', help='query text (or use --def)')
    ap.add_argument('--def', dest='define', metavar='WORD',
                    help='show the full record for one word')
    ap.add_argument('--topk', type=int, default=10)
    ap.add_argument('--ring', type=int, choices=[0, 1])
    ap.add_argument('--cat', help='sub-database: operations, '
                    'things_general, things_picturable, qualities_general, '
                    'qualities_opposites, ring1')
    args = ap.parse_args()

    # --def WORD: straight record lookup, no vectors needed
    if args.define:
        target = args.define.lower()
        found = False
        for doc in (json.load(open(SEED, encoding='utf-8')),
                    json.load(open(RING1, encoding='utf-8'))):
            for e in doc.get('primes', doc.get('words', [])):
                if e['word'] == target:
                    txt = e.get('gloss', e.get('def', ''))
                    print(f"#{e['id']}: {e['word']} "
                          f"[ring {e.get('ring', '?')} {e.get('cat', '')}]")
                    wrap = re.findall(r'.{1,72}(?:\s|$)', txt)
                    print('\n'.join('    ' + w.rstrip() for w in wrap))
                    found = True
        if not found:
            print(f"'{target}' is not in the network yet")
        return 0

    query = ' '.join(args.query).strip()
    if not query:
        ap.print_help()
        return 1

    if not DB.exists():
        print('run embed.py first (no hai.db in toolbelt/)')
        return 1

    qvecs, backend = embed_texts([query], 'auto')
    qvec = qvecs[0]
    sql = 'SELECT id, word, ring, pos, cat, text, vec FROM words'
    cond, params = [], []
    if args.ring is not None:
        cond.append('ring = ?'); params.append(args.ring)
    if args.cat:
        cond.append('cat = ?'); params.append(args.cat)
    if cond:
        sql += ' WHERE ' + ' AND '.join(cond)
    con = sqlite3.connect(DB)
    rows = con.execute(sql, params).fetchall()
    scored = []
    for rid, word, ring, pos, cat, text, blob in rows:
        v = struct.unpack(f'{len(blob) // 8}d', blob)
        scored.append((cosine(qvec, v), rid, word, ring, cat, text))
    scored.sort(reverse=True)

    print(f'query: {query!r}')
    print(f'sub-database: {args.cat or args.ring or "all"} '
          f'({len(rows)} words scanned)\n')
    for sim, rid, word, ring, cat, text in scored[:args.topk]:
        print(f'  #{rid:<4d} {word:<12s} ring{ring}  {cat:<20s} '
              f'{sim:.3f}  {text[:48]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
