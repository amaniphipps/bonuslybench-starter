# BonuslyBench — an open harness for benchmarking LLMs on your own GTM/RevOps (or any) test set.

Fork it, supply your own connectors + tests, plug in your keys, and run the same
structure Amani used for the original BonuslyBench. Samples included; swap in your data.

## What you get

- **Parallel runner** (`bonuslybench/run_bench.py`) — N models x M tests, caching, retry with
  credit-aware backoff, per-call usage telemetry (tokens, latency, tok/s), error journals.
- **Deterministic scorers** (`bonuslybench/scorers.py`) — named pass/fail checks per test,
  plus a fabrication guard that flags invented entity aliases. No LLM-as-judge by default.
- **Pluggable providers** — OpenRouter direct (REST, just needs `OPENROUTER_API_KEY`), or the
  `hermes -z` CLI path that also handles Anthropic/other Hermes providers. Add your own template.
- **Sample tests** (`tests/tests.json`) — two tests you can run end-to-end out of the box to
  validate your connector before writing your own.

## Quick start

```bash
git clone <repo-url> && cd bonuslybench-starter
cp .env.example .env          # add OPENROUTER_API_KEY
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Single run:

```bash
python3 bonuslybench/run_bench.py models/sample_batch.json --provider openrouter-direct --workers 8
```

Score + rank:

```bash
python3 bonuslybench/scorers.py run_$(date +%Y-%m-%d)
```

That's it. Responses land in `<run_dir>/responses`, usage telemetry in `<run_dir>/usage`,
error journals in `<run_dir>/results/*.err.json`, and per-test scores in
`<run_dir>/results/*.score.json`.

**Validated**: smoke-tested end-to-end with `z-ai/glm-5.3-flash` on 2026-09-16 — the
scorer correctly caught a real arithmetic slip the model made (total/median wrong).
Cost per sample call ≈ $0.00025.

## Bring your own tests

Tests live in `tests/tests.json`. Each entry:

```json
{
  "id": "my-test-id",
  "category": "reporting-analytics",
  "timeout": 120,
  "prompt": "You are a GTM analyst. Use only the data below..."
}
```

Rules of thumb from the original run:
- Keep `id` stable — scorers branch on it.
- Embed every fact the model needs in the prompt (connectors are *your* job — the harness
  never invents data).
- For deterministic scoring, register a matching `if test_id == 'my-test-id':` block inside
  `bonuslybench/scorers.py`.

## Connectors & providers

Providers are just command templates with `{prompt}`, `{model}`, `{usage_file}` placeholders.
Built-ins:

| provider      | what you need                         |
|---------------|----------------------------------------|
| `openrouter-direct` | `OPENROUTER_API_KEY` in `.env` (default; cheapest and simplest path) |
| `hermes-openrouter` | `hermes` CLI + `hermes auth login` on OpenRouter      |
| `hermes-anthropic`  | `hermes` CLI + Anthropic provider configured       |

Add your own by extending `PROVIDERS` in `bonuslybench/run_bench.py`.

## Cost & telemetry

Usage files capture tokens and cost (OpenRouter returns `usage.cost`).
Latency and tok/s are joined per response. The original BonuslyBench processed
102 models for ~$764 — cost discipline is a first-class feature here.

## Sample results → publication

The original site (bonuslybench.com) was built from these JSON artifacts, so you can
turn your own `results/*.score.json` into a static report or scoreboard without touching
an LLM judge.
