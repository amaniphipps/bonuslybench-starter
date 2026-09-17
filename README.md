# BonuslyBench

**An open harness for benchmarking LLMs on your own workflows — the same
structure behind the [BonuslyBench study](https://www.bonuslybench.com): 40 tests,
102 models.**

## Why this exists

We use open source models at Bonusly. We have for months (as of the time of this writing). The problem was never whether
to try them — it's that there are so many, and it's hard to know which ones are any good,
at what, and how they differ in costs. 

I also wanted a more definitive answer to the bigger question: whether a team should be
using open models at all. At this point, I think the answer still is "it depends". It depends on where the rest of the industry is, what solutions are available, where your team is, and your actual use cases. There are plenty of situations where an
open model is the sensible choice. There are others where Claude or an OpenAI model is
perfectly fine, and some where the right answer is not using AI for that task. I really just loved the idea of having real data to drive my decisions.

The benchmarks that already exist, whether llm-stats, openrouter, vellum, etc. just covered the general areas of work. They're good benchmarks, but they're generic. What I kept asking was: for my work, in my actual workflows, how does this model
do? If I'm picking a model to run data enrichment, record management, and CRM cleanup
through an agent, I wanted to see if there was a material difference with evidence from that kind of task — not from a generic test.

So we built our own. Forty tests, drawn from real skills we've deployed in our own
Bonusly instance and use day to day. We anonymized the data so it belongs to no one in
particular, kept the mess that makes the work hard, and ran the tests across a wide range
of models. Everything is compared against Claude Sonnet 5, because that's a solid
baseline for most people's everyday work and it's what we run today. The tests, the data,
the answer keys, every response, and every score are all published in the
[BonuslyBench report](https://www.bonuslybench.com) — updated once a month as new models
release.

That's the why. It's curiosity, mostly. This world changes every few weeks, and I'd
rather ground our assumptions in something we can check and find out we were wrong than
keep guessing and never know. We talk about this stuff constantly inside Bonusly, so
putting it out in the open felt like the natural next step.

**What this repo is:** the harness we used, minus our data. The parallel runner, the
deterministic scorers, the provider templates, and ten sample tests drawn from the same
categories as the real suite. You bring the connectors, the tests, and the keys — then
take it, run it on your own tasks, and tell me where it's wrong.

— Amani Phipps, Senior Revenue Architect at Bonusly

## What the study found (short version)

- **102 models** tested via OpenRouter — 95 completed all 40 tests, 7 documented partials
- **Top overall:** `muse-spark-1.1` (0.977) · **Best cost-for-value:** `glm-5.3-flash` (0.968 @ $0.28 total)
- **`gpt-5.5-pro` cost $123.62** without leading on accuracy
- **20 of 103 models fabricated at least one answer** — no model is safe to run unvalidated against your CRM

Full results, updated monthly: [bonuslybench.com](https://www.bonuslybench.com)

## Design principles

1. **No LLM-as-judge.** Every check is a named, deterministic pass/fail assertion. If you
   can't score it deterministically, the test isn't finished.
2. **Fabrication is a first-class failure.** Every response is scanned for entity aliases
   that don't exist in the source data. Invented deals = automatic flag.
3. **Cost is a metric, not an afterthought.** Every call records tokens, latency, tok/s,
   and dollars. Rankings without cost are only half the answer.
4. **Partials are documented, not hidden.** One final retry, then the straggler test is
   discarded and documented at exact counts.
5. **Your data, your tests, your keys.** This repo ships mock tests only. The value is
   the structure — you bring the questions your business actually needs answered.

## The report refreshes monthly

The live report at [bonuslybench.com](https://www.bonuslybench.com) re-runs on the 1st
of every month: new OpenRouter chat models released since the last run get added, models
still on the list that haven't been run in over two months get re-run, and the oldest
models roll off once the list passes ~120. The "last run" date on the site is stamped
at deploy time. (That pipeline — `monthly/registry.py` + `monthly/refresh.py` — runs
against our private copy of the suite; the same incremental-refresh pattern is easy to
adapt if you want it for your own fork.)

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
