#!/usr/bin/env python3
"""SIGIL ring-2 generator v2 — defines new words using ONLY rings 0+1.

Pipeline per chunk:
  1. GEN: batches of 40 candidate words -> LLM writes 'word: definition'
     under a closed-vocabulary contract (with examples + trap list).
  2. VALIDATE: every definition token is resolved with validator.py's
     own resolver. Valid -> done.jsonl (checkpoint).
  3. REPAIR: invalid definitions go back to the LLM in small groups with
     the EXACT offending tokens named, plus the substitution table.
  4. Attempts persist in attempts.json; a word is dropped for good after
     8 cumulative failures (expected <1% of candidates).

Run in chunks:   timeout 580 python3 gen_ring2.py
Resume-safe:     done.jsonl is the checkpoint.

Outputs:
  done.jsonl      {'id','word','def'} for every valid word
  attempts.json   {'word': n_failures} persistent counter
  gen.log         progress
  COMPLETE printed when nothing is left
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).parent          # tools/ring2
HAI = pathlib.Path(__file__).resolve().parent.parent / 'seed'
CAND = HERE / 'candidates.jsonl'
DONE = HERE / 'done.jsonl'
ATT = HERE / 'attempts.json'
LOG = HERE / 'gen.log'
TMP = pathlib.Path('/tmp/ring2_call.json')

SOFT_SECONDS = float(os.environ.get('RING2_SECONDS', 540))
GEN_BATCH = int(os.environ.get('RING2_BATCH', '80'))
REPAIR_BATCH = 10
MAX_ATTEMPTS = 8
PACE = float(os.environ.get('RING2_PACE', '45'))  # s between LLM calls

# ---------------- allowed vocabulary (rings 0 + 1 + free machinery) -------
seed_doc = json.load(open(HAI / 'seed.json', encoding='utf-8'))
ring1_doc = json.load(open(HAI / 'ring1.json', encoding='utf-8'))
wl = json.load(open(HAI / 'whitelist.json', encoding='utf-8'))

r0 = [e['word'].lower() for e in seed_doc['primes']]
r1 = [e['word'].lower() for e in ring1_doc['words']]
free = [w.lower() for tier, items in wl.items() for w in items]

BASE = set(r0) | set(r1)
WL = set(free)
VOCAB = sorted(BASE | set(free))

sys.path.insert(0, str(HAI))
import validator  # noqa: E402  (the real resolver, shared with repo)

R0_LIST = ', '.join(sorted(r0))

SYSTEM = (
    'You are the dictionary writer for SIGIL, a word-store in which every '
    'new word must be defined using ONLY words that already exist in the '
    'store. You write ring 2: ordinary English words, each defined strictly '
    'from the ring-0 and ring-1 vocabulary in the ALLOWED VOCABULARY and '
    'FREE FORMS lists of the user message.\n\n'
    'FORBIDDEN, however common: big, large, many, can, comfortable, '
    'particular, fun, city, area, job, main, single, happen, subject, '
    'relating, usually, really, typically, located, especially, various, '
    'several, certain, simply. Use great instead of big and large, much '
    'or a great number instead of many, able to instead of can, town '
    'instead of city, part or land instead of area, work instead of job, '
    'chief instead of main, one instead of single, take place instead of '
    'happen, thing talked about instead of subject, at all times or '
    'generally instead of usually, in fact instead of really.\n\n'
    'RULES:\n'
    '1. Every word of every definition must be from the ALLOWED VOCABULARY '
    'or FREE FORMS list in the user message, or one of those words with the '
    'endings -s, -es, -ed, -d, -ing, -er, -est, -ied (started, makes, '
    'running, copied are fine). If unsure a word is allowed, do not use '
    'it: write a different, simpler definition instead.\n'
    '2. Output one line per word, exactly: word: definition\n'
    '3. Definitions are 8 to 16 words, all lowercase, no capitals, no '
    'hyphens, no parentheses, no quotation marks, no periods. Commas ok.\n'
    '4. Varied dictionary style. Correct examples:\n'
    '   home: the place where one is living, the place one goes back to at '
    'the end of the day\n'
    '   city: a town that is very great in size and in the number of its '
    'people and buildings\n'
    '   writer: one who does writing as work, the maker of a book or a '
    'story\n'
    '5. Define every word in the given list; no commentary, no headings.'
)

VOCAB_BLOCK = (
    'ALLOWED VOCABULARY (ring 0 + ring 1):\n' +
    ', '.join(sorted(BASE | set(free))) +
    '\n\nFREE FORMS you may also use:\n' + ', '.join(sorted(WL))
)

LINE_RE = re.compile(r'^\s*([a-z]+)\s*:\s*(.+?)\s*$')


def call_llm(user_prompt):
    last = None
    for attempt in range(4):
        cp = subprocess.run(
            ['z-ai', 'chat', '-s', SYSTEM, '-p', user_prompt, '-o', str(TMP)],
            capture_output=True, text=True, timeout=300)
        if cp.returncode == 0 and TMP.exists():
            try:
                return json.load(open(TMP))['choices'][0]['message']['content']
            except Exception as e:
                last = e
                continue
        last = cp.stderr[-200:]
        # 429 / transient failure -> exponential backoff
        wait = min(20 * (2 ** attempt), 120)
        log(f'llm call failed (attempt {attempt + 1}), backing off {wait}s')
        time.sleep(wait)
    raise RuntimeError(f'z-ai call failed: {last}')


def paced_llm(user_prompt):
    out = call_llm(user_prompt)
    time.sleep(PACE)
    return out


def parse_defs(reply):
    out = {}
    for line in reply.split('\n'):
        line = line.strip().lower()
        if not line:
            continue
        m = LINE_RE.match(line)
        if not m:
            continue
        w, d = m.group(1), m.group(2)
        d = d.strip().rstrip('.').strip()
        d = re.sub(r'\s+', ' ', d)
        out[w] = d
    return out


def offending(d):
    return [t for t in validator.tokens(d)
            if validator.resolve(t, BASE, WL) is None]


def valid_def(d):
    if not (8 <= len(d.split()) <= 24):
        return False
    return not offending(d)


def load_state():
    done = {}
    if DONE.exists():
        for line in DONE.read_text(encoding='utf-8').splitlines():
            if line.strip():
                rec = json.loads(line)
                done[rec['word']] = rec
    cands = [json.loads(l) for l in
             CAND.read_text(encoding='utf-8').splitlines() if l.strip()]
    att = json.loads(ATT.read_text()) if ATT.exists() else {}
    return cands, done, att


def save_state(done, att):
    pass  # done.jsonl is appended incrementally; attempts saved on change


def log(msg):
    stamp = time.strftime('%H:%M:%S')
    line = f'[{stamp}] {msg}'
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def main():
    t_end = time.time() + SOFT_SECONDS
    cands, done, att = load_state()
    att_dirty = False
    log(f'start: {len(cands)} candidates | done {len(done)} | '
        f'failed-once {len(att)}')

    cand_word = {c['word']: c for c in cands}

    def accept(w, d):
        rec = cand_word[w]
        with open(DONE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(
                {'id': rec['id'], 'word': w, 'def': d}) + '\n')
        done[w] = d

    while time.time() < t_end:
        todo = [w for w in cand_word
                if w not in done and att.get(w, 0) < MAX_ATTEMPTS]
        # fresh words first (frequency order), retries after
        todo.sort(key=lambda w: att.get(w, 0))
        if not todo:
            left = sum(1 for w in cand_word
                       if w not in done and att.get(w, 0) >= MAX_ATTEMPTS)
            log(f'COMPLETE (dropped for good: {left})')
            print('COMPLETE')
            if att_dirty:
                ATT.write_text(json.dumps(att))
            return

        # ---------- 1. GEN round ----------------------------------------
        batch = todo[:GEN_BATCH]
        try:
            reply = paced_llm(
                VOCAB_BLOCK +
                '\n\nDefine these words, one per line, word: definition\n' +
                '\n'.join(batch) +
                '\n\nRemember: only allowed-vocabulary words and free forms '
                '(endings -s -es -ed -d -ing -er -est -ied), no other '
                'English words at all.')
        except Exception as e:
            log(f'gen call error: {e} — sleeping 15s')
            time.sleep(15)
            continue
        defs = parse_defs(reply)

        coverage = sum(1 for w in batch if w in defs) / len(batch)
        if coverage < 0.5:
            # degraded / truncated response — do not count as failures
            log(f'degraded response (coverage {coverage:.0%}) — requeueing')
            time.sleep(30)
            continue

        invalid = []
        for w in batch:
            d = defs.get(w)
            if d and valid_def(d):
                accept(w, d)
            else:
                invalid.append((w, d or ''))

        # ---------- 2. REPAIR round (failures named, one pass) ---------
        if invalid and time.time() < t_end:
            groups = [invalid[i:i + REPAIR_BATCH]
                      for i in range(0, len(invalid), REPAIR_BATCH)]
            still = []
            for g in groups:
                if time.time() >= t_end:
                    still.extend(g)
                    continue
                lines = []
                for w, d in g:
                    bad = offending(d) if d else []
                    lines.append(f'{w}: {d}\n'
                                 f'  forbidden words used: '
                                 f'{", ".join(bad) if bad else "(too short or missing)"}')
                try:
                    reply = paced_llm(
                        VOCAB_BLOCK +
                        '\n\nThese definitions break the closed-vocabulary '
                        'rule. Rewrite each one so that EVERY word is from '
                        'the allowed vocabulary or free forms (endings '
                        '-s -es -ed -d -ing -er -est -ied allowed). Replace '
                        'the forbidden words with allowed ones. Keep the '
                        'word: definition form, 8 to 16 words, all '
                        'lowercase.\n\n' + '\n'.join(lines))
                except Exception as e:
                    log(f'repair call error: {e} — sleeping 15s')
                    time.sleep(15)
                    still.extend(g)
                    continue
                rdefs = parse_defs(reply)
                for w, d in g:
                    rd = rdefs.get(w)
                    if rd and valid_def(rd):
                        accept(w, rd)
                    else:
                        still.append((w, rd or d or ''))
            invalid = still

        # ---------- 3. failures recycle into the next gen round ---------
        for w, d in invalid:
            att[w] = att.get(w, 0) + 1
            att_dirty = True
        log(f'gen {len(batch)} | ok {len(batch) - len(invalid)} | '
            f'done {len(done)} | '
            f'remaining {sum(1 for w in cand_word if w not in done and att.get(w, 0) < MAX_ATTEMPTS)}')
        if att_dirty:
            ATT.write_text(json.dumps(att))
            att_dirty = False

    if att_dirty:
        ATT.write_text(json.dumps(att))
    left = sum(1 for w in cand_word
               if w not in done and att.get(w, 0) < MAX_ATTEMPTS)
    log(f'stop: done {len(done)} | remaining {left}')
    print(f'IN PROGRESS: {left} words left — re-run this script')


if __name__ == '__main__':
    main()
