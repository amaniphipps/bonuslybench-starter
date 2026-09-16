#!/usr/bin/env python3
"""BonuslyBench runner — spawns N models x M tests in parallel with telemetry per call.

Generalized from the original BonuslyBench harness. Provider-agnostic: any CLI
that maps to one of the built-in PROVIDERS templates (or your own --cmd-template).
"""
import json, subprocess, time, os, sys, threading, argparse
from concurrent.futures import ThreadPoolExecutor

ERR_SIGS = ('API call failed', 'exceeded the upstream proxy', 'Billing or credits exhausted', 'HTTP 402')

# Each provider template MUST contain {prompt}, {model}, {usage_file}.
# Usage-file-capable providers write token telemetry to --usage-file (see hermes -z).
PROVIDERS = {
    # hermes CLI (original BonuslyBench path, OpenRouter routed)
    'hermes-openrouter': ['hermes', '-z', '{prompt}', '-m', '{model}', '--provider', 'openrouter',
                          '--ignore-rules', '--ignore-user-config', '--safe-mode', '-t', '',
                          '--reasoning', 'low', '--usage-file', '{usage_file}'],
    'hermes-anthropic': ['hermes', '-z', '{prompt}', '-m', '{model}', '--provider', 'anthropic',
                         '--ignore-rules', '--ignore-user-config', '--safe-mode', '-t', '',
                         '--reasoning', 'low', '--usage-file', '{usage_file}'],
    # plain python -u script calling OpenRouter REST directly (no hermes needed)
    'openrouter-direct': ['python3', '-u', 'bonuslybench/call_openrouter.py',
                          '--model', '{model}', '--usage-file', '{usage_file}', '--prompt', '{prompt}'],
}

_lock = threading.Lock()

def _usage_ok(uf):
    try:
        u = json.load(open(uf)) if os.path.exists(uf) else {}
        return (not u.get('failed')), u
    except Exception:
        return True, {}

class Runner:
    def __init__(self, run_dir, cmd):
        self.run = run_dir
        self.cmd = cmd
        for d in ('responses', 'results', 'usage'):
            os.makedirs(f'{run_dir}/{d}', exist_ok=True)

    def run_one(self, model, t):
        tid = t['id']; key = f"{model.replace('/', '__')}__{tid}"
        resp = f'{self.run}/responses/{key}.txt'; uf = f'{self.run}/usage/{key}.json'
        if os.path.exists(resp) and os.path.getsize(resp) > 0 and os.path.exists(uf):
            ok, _ = _usage_ok(uf)
            if ok: return (model, tid, 'cached', 0)
            os.remove(resp)  # stale failed payload -> rerun
        prompt = t['prompt']
        retries = t.get('retries', 4)
        last_err = ''; lat = 0
        for attempt in range(retries):
            start = time.time()
            cmd = [c.format(prompt=prompt, model=model, usage_file=uf) for c in self.cmd]
            try:
                p = subprocess.run(cmd, capture_output=True, text=True, timeout=t.get('timeout', 300))
                out = p.stdout
                lat = time.time() - start
                if p.returncode != 0 or not out.strip():
                    last_err = (p.stderr or out).strip()[:300]
                    if '402' in last_err or 'credit' in last_err.lower():
                        time.sleep(20 * (attempt + 1)); continue
                    break
                if out.lstrip().startswith('API call failed') or any(s in out for s in ERR_SIGS):
                    last_err = out.strip().split('\n')[0][:200]
                    if '402' in last_err or 'credit' in last_err.lower():
                        time.sleep(20 * (attempt + 1)); continue
                    break
                ok, u = _usage_ok(uf)
                if not ok:
                    last_err = 'usage-file-marked-failed'
                    if attempt < retries - 1:
                        time.sleep(10 * (attempt + 1)); continue
                open(resp, 'w').write(out)
                try:
                    u = json.load(open(uf)) if os.path.exists(uf) else {}
                    u['latency_s'] = round(lat, 2)
                    ot = u.get('output_tokens') or 0
                    u['tok_per_s'] = round(ot / lat, 1) if lat > 0 and ot else None
                    json.dump(u, open(uf, 'w'), indent=1)
                except Exception:
                    pass
                return (model, tid, 'ok', lat)
            except subprocess.TimeoutExpired:
                last_err = 'timeout'; lat = t.get('timeout', 300)
                break
        with _lock:
            json.dump({'model': model, 'test': tid, 'error': last_err[:300], 'latency': lat},
                      open(f'{self.run}/results/{key}.err.json', 'w'))
        if os.path.exists(resp):
            os.remove(resp)
        return (model, tid, 'error:' + last_err[:80], lat)

def main():
    ap = argparse.ArgumentParser(description='BonuslyBench runner')
    ap.add_argument('models_file', help='JSON list of {"id": "...", "tier": "..."} model entries')
    ap.add_argument('--tests', default='tests/tests.json')
    ap.add_argument('--provider', default='openrouter-direct',
                    help=f"built-ins: {', '.join(PROVIDERS)} — or extend PROVIDERS and pass your own")
    ap.add_argument('--run-dir', default=None, help='defaults to run_<YYYY-MM-DD>')
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--only-test', default=None)
    args = ap.parse_args()
    if args.provider not in PROVIDERS:
        ap.error(f"unknown provider '{args.provider}'. Built-ins: {', '.join(PROVIDERS)}. "
                 "To add your own, extend PROVIDERS in run_bench.py.")

    run_dir = args.run_dir or f'run_{time.strftime("%Y-%m-%d")}'
    tests = json.load(open(args.tests))
    models = [m['id'] if isinstance(m, dict) else m for m in json.load(open(args.models_file))]
    tests = [t for t in tests if (args.only_test is None or t['id'] == args.only_test)]
    jobs = [(m, t) for m in models for t in tests]
    print(f'provider={args.provider} models={len(models)} tests={len(tests)} jobs={len(jobs)} workers={args.workers}', flush=True)

    runner = Runner(run_dir, cmd=PROVIDERS[args.provider])
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for model, tid, status, lat in ex.map(lambda j: runner.run_one(*j), jobs):
            done += 1
            print(f'[{done}/{len(jobs)}] {model} :: {tid} -> {status} ({lat:.0f}s)', flush=True)

if __name__ == '__main__':
    main()
