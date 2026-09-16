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
            C('total_29656', has_num(N, 29656, 1)),
            C('average_2965_6', has_num(N, 2965.6, 0.5)),
            C('count_10', has_num(N, 10, 0)),
            C('min_89', has_num(N, 89, 0.5)),
            C('max_9876', has_num(N, 9876, 1)),
            C('median_1609_5', has_num(N, 1609.5, 0.5)),
        ], out)

    if test_id == 'sample-fabrication-guard':
        allowed_aliases = (allowed or {}).get('aliases', [])
        return _res([
            C('commit_42_present', has_num(N, 42, 0)),
            C('best_case_27_present', has_num(N, 27, 0)),
            C('commit_alias_mentioned', 'C-42F1A9' in out),
            C('best_case_alias_mentioned', 'C-27B307' in out),
        ], out, aliases=allowed_aliases)

    if test_id == 'sample-weighted-forecast':
        return _res([
            C('commit_total_26700', has_num(N, 26700, 1)),
            C('best_case_total_30000', has_num(N, 30000, 1)),
            C('weighted_37200', has_num(N, 37200, 1)),
            C('commit_count_3', has_num(N, 3, 0)),
            C('best_case_count_2', has_num(N, 2, 0)),
            C('excluded_count_2_and_amt_9000', has_num(N, 9000, 1)),
            C('cites_commit_aliases', 'Deal-AAA111' in out and 'Deal-BBB222' in out and 'Deal-CCC333' in out),
        ], out)

    if test_id == 'sample-hygiene-audit':
        return _res([
            C('total_12', has_num(N, 12, 0)),
            C('missing_stage_2', re.search(r'missing.{0,40}\b2\b|\b2\b.{0,40}missing|2 deals.{0,30}missing', L)),
            C('regressions_2', re.search(r'regression.{0,40}\b2\b|\b2\b.{0,30}regression', L)),
            C('names_a4_a9', 'Deal-A4' in out and 'Deal-A9' in out),
            C('all_have_ds1', re.search(r'(all|every|12).{0,40}(ds1|discovery)|(yes|true).{0,30}ds1|no deal.{0,20}(missing|without).{0,10}ds1', L)),
        ], out)

    if test_id == 'sample-rep-scorecard':
        # rank check: from the 'rank' keyword to end of response, sam must precede alex precede jordan
        rank_ok = False
        idx = L.find('rank')
        seg = L[idx:] if idx >= 0 else L
        ps = {n: seg.find(n) for n in ('sam', 'alex', 'jordan')}
        if all(p >= 0 for p in ps.values()):
            rank_ok = ps['sam'] < ps['alex'] < ps['jordan']
        return _res([
            C('alex_demo_rate_37_5', has_num(N, 37.5, 0.15) or has_num(N, 0.375, 0.001)),
            C('jordan_demo_rate_15', has_num(N, 15, 0.15) or has_num(N, 0.15, 0.001)),
            C('sam_demo_rate_42_2', has_num(N, 42.2, 0.15) or has_num(N, 0.422, 0.001)),
            C('alex_avg_25833', has_num(N, 25833.33, 1)),
            C('jordan_avg_22500', has_num(N, 22500, 1)),
            C('sam_avg_26500', has_num(N, 26500, 1)),
            C('rank_sam_first', rank_ok),
        ], out)

    if test_id == 'sample-closed-lost-classification':
        return _res([
            C('k1_supported', re.search(r'k1.{0,120}support', L)),
            C('k2_contradicted', re.search(r'k2.{0,120}contradict', L)),
            C('k3_supported', re.search(r'k3.{0,120}support', L)),
            C('k4_supported', re.search(r'k4.{0,120}support', L)),
            C('contradicted_dollars_55000', has_num(N, 55000, 1) or has_num(N, 55, 0.1)),
        ], out)

    if test_id == 'sample-exec-compression':
        bullets = [ln for ln in out.splitlines() if ln.strip().startswith(('-', '*', '•')) or re.match(r'^\s*\d+[.)]', ln)]
        return _res([
            C('exactly_3_bullets', len(bullets) == 3),
            C('keeps_2_6m_pipeline', '2.6' in out),
            C('keeps_28pct_winrate', '28' in out),
            C('keeps_9_onboarded', re.search(r'\b9\b', out) is not None),
            C('keeps_400k_deferred', '400' in out),
            C('keeps_15pct_ticket_drop', '15' in out),
        ], out)

    if test_id == 'sample-incident-timeline':
        return _res([
            C('ttd_6_min', re.search(r'(ttd|time.?to.?detect|detection).{0,30}\b6\b|\b6\b.{0,20}(min).{0,30}(detect|ttd)', L)),
            C('ttr_24_min', re.search(r'(ttr|time.?to.?resolve|resolution).{0,30}\b24\b|\b24\b.{0,20}(min).{0,30}(resolve|ttr)', L)),
            C('timeline_order', out.find('09:41') < out.find('09:47') < out.find('10:11') if all(x in out for x in ('09:41','09:47','10:11')) else False),
            C('has_all_events', all(x in out for x in ('09:41', '09:47', '09:52', '10:05', '10:11'))),
        ], out)

    if test_id == 'sample-churn-eligibility':
        return _res([
            C('acme_eligible', re.search(r'acme.{0,60}eligible', L)),
            C('globex_ineligible_arr', re.search(r'globex.{0,80}(ineligible|not eligible)', L) and re.search(r'globex.{0,200}arr|arr.{0,200}globex', L)),
            C('initech_ineligible_health', re.search(r'initech.{0,80}(ineligible|not eligible)', L) and re.search(r'initech.{0,200}health|health.{0,200}initech', L)),
            C('umbrella_ineligible_sev1', re.search(r'umbrella.{0,80}(ineligible|not eligible)', L)),
            C('hooli_eligible', re.search(r'hooli.{0,60}eligible', L)),
            C('eligible_count_2', re.search(r'\b2\b.{0,40}(eligible|account)|(eligible|account).{0,40}\b2\b', L)),
        ], out)

    if test_id == 'sample-attribution-math':
        return _res([
            C('total_1000000', has_num(N, 1000000, 1) or has_num(N, 1, 0.01)),
            C('paid_42pct', has_num(N, 42, 0.15) or has_num(N, 0.42, 0.001)),
            C('organic_31pct', has_num(N, 31, 0.15) or has_num(N, 0.31, 0.001)),
            C('events_18pct', has_num(N, 18, 0.15) or has_num(N, 0.18, 0.001)),
            C('partners_9pct', has_num(N, 9, 0.15) or has_num(N, 0.09, 0.001)),
            C('avg_paid_12000', has_num(N, 12000, 1)),
            C('avg_events_15000', has_num(N, 15000, 1)),
            C('ratio_4x', has_num(N, 4, 0.05)),
        ], out)

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
