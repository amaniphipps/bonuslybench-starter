# Architecture

The harness is a three-stage pipeline with no LLM judge:

1. **`tests/tests.json`** — the test catalog. Each entry has `id`, `category`,
   `prompt`, `timeout`. Prompts embed all source-of-truth data inline, so the
   harness never invents facts (connectors solve *how* you got the data — file,
   warehouse pull, CSV render — the runtime only sees a finished prompt).

2. **`bonuslybench/run_bench.py`** — spawns (model, test) pairs in a thread pool.
   For each pair it:
   - caches by checksum file (`responses/
<model>__<test>.txt`) to make re-runs idempotent,
   - retries with credit-aware backoff on 402/credit errors and on usage-file-marked failures,
   - stamps latency and tok/s into the usage JSON,
   - journals errors in `results/<key>.err.json`.

3. **`bonuslybench/scorers.py`** — deterministic checks per test id. Each check is a
   named boolean (`'total_42'`), so a `.score.json` is auditable. The fabrication
   guard flags any `(Deal|C)-[0-9A-F]{4,8}` alias not found in the allowed-aliases
   list you feed it.

```
models/sample_batch.json ──▶ run_bench.py ──▶ responses/*.txt + usage/*.json
                                                           │
tests/tests.json ──────────▶ scorers.py ───▶ results/*.score.json
                                                           └▶ aggregated ranking (stdout)
```

## Extending

- **New provider**: add a `PROVIDERS[name]` template in `run_bench.py`.
- **Own connector**: resolve `prompt` into final text *outside* the runner — pull
  from your CRM warehouse, CSV, or API, then materialize `tests.json`. The runner
  should never call connectors.
- **Richer reports**: read `results/*.score.json` and render HTML; the original
  `BonuslyBench_Final_Report.html` was produced by that same pattern.
