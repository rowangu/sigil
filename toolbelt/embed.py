#!/usr/bin/env python3
"""HAI toolbelt — embed.py: put every word of the network into vector space.

The toolbelt is the learner's side of HAI (the fixed core never grows;
this file may change freely). It reads seed.json + ring1.json, embeds each
word (word + definition text), and stores the vectors in an SQLite
database for lookup.py.

Backends (first available wins):
  1. ollama   — nomic-embed-text served at localhost:11434
                (ollama pull nomic-embed-text)
  2. hash     — deterministic 256-dim char-trigram hashing. No network,
                bit-exact across machines, good enough to demo retrieval.
                NOT semantic: swap in the ollama backend for real work.

Usage:
    python3 embed.py                 # (re)build toolbelt/hai.db
    python3 embed.py --backend hash # force the offline backend
"""
import argparse
import json
import math
import pathlib
import sqlite3
import sys
import time
import urllib.request

HERE = pathlib.Path(__file__).parent
SEED = HERE.parent / 'seed' / 'seed.json'
RING1 = HERE.parent / 'seed' / 'ring1.json'
DB = HERE / 'hai.db'

DIMS = 256


def ollama_available(host='http://localhost:11434'):
    try:
        urllib.request.urlopen(host + '/api/tags', timeout=1)
        return True
    except Exception:
        return False


def embed_ollama(texts):
    import json as _json
    body = _json.dumps({'model': 'nomic-embed-text', 'input': texts}).encode()
    req = urllib.request.Request(
        'http://localhost:11434/api/embed',
        data=body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as r:
        out = _json.load(r)
    return [v[:DIMS] if len(v) > DIMS else v + [0.0] * (DIMS - len(v))
            for v in out['embeddings']]


def _h(s):
    import hashlib
    return int.from_bytes(hashlib.blake2b(s.encode('utf-8', 'ignore'),
                                           digest_size=8).digest(), 'big')


def embed_hash(texts):
    out = []
    for text in texts:
        v = [0.0] * DIMS
        t = ' ' + text.lower() + ' '
        for i in range(len(t) - 2):
            tri = t[i:i + 3]
            v[_h(tri) % DIMS] += 1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        out.append([x / n for x in v])
    return out


def embed_texts(texts, backend):
    if backend == 'ollama' or (backend == 'auto' and ollama_available()):
        return embed_ollama(texts), 'ollama:nomic-embed-text'
    return embed_hash(texts), 'hash:char-trigram(deterministic)'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--backend', choices=['auto', 'ollama', 'hash'],
                    default='auto')
    args = ap.parse_args()

    seed = json.load(open(SEED, encoding='utf-8'))
    ring1 = json.load(open(RING1, encoding='utf-8'))

    rows = []
    for e in seed['primes']:
        rows.append((e['id'], e['word'], 0, e['pos'], e['cat'],
                     f"{e['word']}: {e['gloss']}"))
    for e in ring1['words']:
        rows.append((e['id'], e['word'], 1, e['pos'], 'ring1',
                     f"{e['word']}: {e['def']}"))

    t0 = time.time()
    vecs, used = embed_texts([r[5] for r in rows], args.backend)
    dt = time.time() - t0

    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    con.execute('CREATE TABLE words ('
                'id INTEGER PRIMARY KEY, word TEXT, ring INTEGER, '
                'pos TEXT, cat TEXT, text TEXT, vec BLOB)')
    import struct
    con.executemany(
        'INSERT INTO words VALUES (?,?,?,?,?,?,?)',
        [(*r, struct.pack(f'{len(v)}d', *v)) for r, v in zip(rows, vecs)])
    con.execute('CREATE TABLE meta ('
                'key TEXT PRIMARY KEY, value TEXT)')
    con.executemany('INSERT INTO meta VALUES (?,?)', [
        ('backend', used), ('dimensions', str(DIMS)),
        ('words', str(len(rows))), ('built', time.strftime('%Y-%m-%d %H:%M')),
    ])
    con.commit()
    con.close()
    print(f'embedded {len(rows)} words with backend {used} in {dt:.1f}s')
    print(f'wrote {DB}')
    if used.startswith('hash'):
        print('note: hash backend is a placeholder — install ollama + '
              'nomic-embed-text for real semantics')


if __name__ == '__main__':
    sys.exit(main())
