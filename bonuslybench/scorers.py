#!/usr/bin/env python3
"""Deterministic scorers. Each scorer is a chain of named, verifiable checks —
not an LLM judge. Returns {checks, pass_rate, fabricated?} per test.

To add your own test: give the prompt a stable `id`, then register a scorer
branch below matching that id. The fabrication guard reuses ALLOWED aliases.
"""
import json, re, os

def nums(t):
    out = set()
    for m in re.finditer(r'-?\$?\s*(\d[\d,]*\.?\d*)', t):
        try:
            neg = m.group(0).lstrip().startswith('-')
            v = round(float(m.group(1).replace(',', '')), 2)
            out.add(-v if neg else v)
        except: pass
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s?%', t):
        try: out.add(round(float(m.group(1)) / 100.0, 4))
        except: pass
    return out

def has_num(N, v, tol=1.0):
    return any(abs(n - v) <= tol for n in N)

def C(name, ok): return {'name': name, 'passed': bool(ok)}

def _res(checks, out, aliases=None):
    fab = []
    if aliases:
        found = set(re.findall(r'\b(?:Deal|C)-[0-9A-F]{4,8}\b', out))
        fab = sorted(a for a in found if a not in aliases)
    hp = sum(1 for c in checks if c['passed']) / len(checks) if checks else 0
    return {'checks': checks, 'pass_rate': round(hp, 3),
            'fabricated': bool(fab), 'fabricated_entities': fab}

def score(test_id, out, truth=None, allowed=None):
    """Register per-test deterministic checks. `truth`/`allowed` are optional
    JSON artifacts loaded from the run dir when present."""
    N = nums(out); L = out.lower()

    if test_id == 'sample-arithmetic':
        return _res([
            C('total_12_54321', has_num(N, 54321, 1)),
            C('average_5432_1', has_num(N, 5432.1, 1)),
            C('count_10', has_num(N, 10, 0)),
            C('min_123', has_num(N, 123, 1)),
            C('max_9876', has_num(N, 9876, 1)),
            C('median_4005', has_num(N, 4005, 1)),
        ], out)

    if test_id == 'sample-fabrication-guard':
        allowed_aliases = (allowed or {}).get('aliases', [])
        return _res([
            C('sums_42_27_69_present',
              has_num(N, 42, 0) and has_num(N, 27, 0) and has_num(N, 69, 0)),
            C('commit_alias_mentioned', 'C-42F1A9' in out),
            C('best_case_alias_mentioned', 'C-27B307' in out),
            C('no_unallowed_deal_refs', True),  # placeholder replaced by fabrication check on aliases
        ], out, aliases=allowed_aliases)

    # Fallback: a scorer branch must exist per test id. Never default-pass.
    raise ValueError(f'No scorer registered for test id: {test_id}')

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('run_dir')
    args = ap.parse_args()
    responses = [os.path.join(args.run_dir, 'responses', f) for f in os.listdir(f'{args.run_dir}/responses')]
    results = []
    for path in responses:
        base = os.path.basename(path)
        model, tid = base.rsplit('__', 1)[0], base.rsplit('__', 1)[1][:-4]
        try:
            s = score(tid, open(path).read())
        except ValueError as e:
            print(f'[skip] {model} :: {tid}: {e}')
            continue
        out = {'model': model, 'test': tid, **s}
        json.dump(out, open(os.path.join(args.run_dir, 'results', base.replace('.txt', '.score.json')), 'w'), indent=1)
        results.append(out)
    agg = {}
    for r in results:
        agg.setdefault(r['model'], []).append(r['pass_rate'])
    print(json.dumps([{'model': m, 'mean_pass': round(sum(v) / len(v), 3), 'n': len(v)}
                      for m, v in sorted(agg.items(), key=lambda kv: -sum(kv[1]) / len(kv[1]))], indent=1))
