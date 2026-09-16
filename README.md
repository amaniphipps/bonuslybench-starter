# BonuslyBench — an open harness for benchmarking LLMs on your own GTM/RevOps (or any) test set.

Fork it, supply your own connectors + tests, plug in your keys, and run the same
structure Amani used for the original BonuslyBench. Samples included; swap in your data.

## Why this exists

In 2026 the LLM market crossed a threshold where "which model should RevOps actually buy?"
stopped having an obvious answer. Frontier models cost 100–400x more per call than the
best open-source options, yet nearly all public benchmarks (MMLU, GSM8K, HumanEval) test
academic knowledge or competitive programming — not the thing a GTM team actually asks a
model to do: read a messy CRM export, catch a stage regression, weight a forecast
correctly, and *not invent a deal that doesn't exist*.

So the original **BonuslyBench** study (September 2026) was built to answer one question
with real numbers: **on 40 deterministic GTM/RevOps tasks drawn from a real pipeline
dataset, which models actually do the work, and what do they cost to do it?**

### What the initial study found

- **102 models tested** via OpenRouter — 95 completed the full suite, 7 documented partials.
- **~$764 total spend** to benchmark the entire field, proving cost-disciplined evaluation
  is possible if you measure per-call token telemetry from the start.
- **Top overall**: `muse-spark-1.1` at 0.977 mean pass rate.
- **Best cost-for-value**: `glm-5.3-flash` at 0.968 for **$0.28 total** — a model that
  would be invisible on capability-only leaderboards.
- **Overpriced at the frontier**: `gpt-5.5-pro` cost $123.62 without leading on accuracy.
- **Smaller open models reliably beat flagship models on deterministic GTM math**, and
  every model was caught by the fabrication guard at least once — no model is safe to
  run unvalidated against your CRM.

Full writeup and live matrix: [bonuslybench.com](https://www.bonuslybench.com)

### Design principles carried into this harness

1. **No LLM-as-judge.** Every check is a named, deterministic pass/fail assertion
   (exact number present, alias cited, regex matched). If you can't score it
   deterministically, the test isn't finished.
2. **Fabrication is a first-class failure.** Every response is scanned for entity
   aliases that don't exist in the source data. Invented deals = automatic flag.
3. **Cost is a metric, not an afterthought.** Every call records tokens, latency,
   tok/s, and dollars. Rankings without cost are only half the answer.
4. **Partials are documented, not hidden.** If a model can't finish the suite, its
   exact completion count is published. Endgame policy: one final retry, then the
   straggler test is discarded and documented.
5. **Your data, your tests, your keys.** This repo ships mock tests only. The value
   is the structure — you bring the connectors and the questions your business
   actually needs answered.

## What you get

- **Parallel runner** (`bonuslybench/run_bench.py`) — N models x M tests, caching, retry with
  credit-aware backoff, per-call usage telemetry (tokens, latency, tok/s), error journals.
- **Deterministic scorers** (`bonuslybench/scorers.py`) — named pass/fail checks per test,
  plus a fabrication guard that flags invented entity aliases. No LLM-as-judge by default.
- **Pluggable providers** — OpenRouter direct (REST, just needs `OPENROUTER_API_KEY`), or the
  `hermes -z` CLI path that also handles Anthropic/other Hermes providers. Add your own template.
- **Sample tests** (`tests/tests.json`) — ten tests you can run end-to-end out of the box
  to validate your connector before writing your own: two smoke tests plus one
  representative task per original BonuslyBench category (forecasting, CRM hygiene,
  rep scorecards, closed-lost classification, exec communication, incident timelines,
  churn eligibility, attribution math). Each has a deterministic scorer branch.

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
