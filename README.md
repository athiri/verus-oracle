# verus-oracle

A verifiability oracle for [Verus](https://github.com/verus-lang/verus). Given a Rust file
as input, it outputs:

- **Verifiability score**: easy / medium / hard (estimated effort to make it `cargo verus verify`).
- **Predicted rewrite pattern(s)**, from a 10-category taxonomy of common Verus rewrites
  (R1 trait→wrapper, R2 chain→named, R3 iterator→loop, R4 std→inline, R5 negation→wrapper,
  R7 cast/reborrow, R8 arithmetic, R9 const→materialized, R10 tuple-struct→named,
  R11 constructor→named).
- **Estimated solver duration**, from a proxy regression on repair-loop turns and
  per-pattern observed difficulty.

The tool gives crypto and systems teams a **triage signal** to find functions worth verifying
without running Verus themselves.

## Why this exists

Formal verification with Verus is high-leverage for crypto/systems code but
expensive to attempt blindly: a Verus run can chew minutes per function and the
repair loop is mostly human. Today there is no cheap triage signal that tells
an engineer **"this function is one rewrite away from verifying"** vs.
**"this will eat your afternoon."**

`verus-oracle` is that signal. It reads the source statically, asks a small
LLM router which of the known Verus rewrite patterns apply, runs cheap yes/no
specialist probes, and emits `{bucket, predicted_pattern, est_duration_s}`,
which is enough to prioritize a backlog of candidate functions without booting
Verus at all.

## Pipeline

```
file.rs ─▶ tree-sitter parse ─▶ static feature extraction ─▶ R-pattern router (LLM)
                                                                     │
                                                                     ▼
                                                    per-pattern specialist questions
                                                       (LLM yes/no probes)
                                                                     │
                                                                     ▼
                                              weighted aggregation + duration proxy
                                                                     │
                                                                     ▼
                                                {score, pattern, est_duration_s}
```

The taxonomy + LLM prompts are **vendored** from `inference-dalek`, a private
research-lab repository (not public) that produced the rewrite taxonomy and the
labeled benchmark used here. A refresh script in
`scripts/refresh_from_dalek.py` re-syncs them when the upstream taxonomy
updates. What's mine vs. borrowed is documented in
[Sources & credits](#sources--credits) below.

## Install

```bash
pip install -e ".[dev,server]"
export ANTHROPIC_API_KEY=...
```

## Usage

CLI:

```bash
verus-oracle path/to/file.rs                       # one file
verus-oracle path/to/file.rs --json                # JSON-only output
verus-oracle path/to/file.rs --offline             # skip LLM stage; static features only
```

Web (optional):

```bash
uvicorn verus_oracle.server:app --port 8000
# then open http://127.0.0.1:8000/  (paste-and-score UI)
# JSON API:  POST /score   {"source": "...", "offline": false}
# Multipart: POST /score/upload  with form field 'file'
# OpenAPI:   http://127.0.0.1:8000/docs
```

Python API:

```python
from verus_oracle import score_source

verdict = score_source(open("field.rs").read())
print(verdict.bucket, verdict.predicted_pattern, verdict.est_duration_s)
```

## Calibration data

Two corpora ship in `data/`:

- `calibration_seed.jsonl`: **37 cases** with observed Verus outcomes
  (`verified`, `wall_s`, `n_observations`) and pre-extracted features.
  The per-pattern difficulty weights and the duration regression in
  `data/duration_proxy.json` are fit from this corpus.
- `live_router_predictions.jsonl` / `..._v2.jsonl`: **107 cases** from the
  full upstream `rewrites_v2.jsonl` benchmark, with router top-1/top-2
  predictions per case. These drive the evaluation below.

## Evaluation

Router accuracy on the full 107-case `rewrites_v2` benchmark (`scripts/live_eval.py`):

| version | top-1 | top-2 |
|---------|------:|------:|
| v1      | 63.6% (68/107) | 82.2% (88/107) |
| v2      | **68.2%** (73/107) | **88.8%** (95/107) |

Most of the v1 → v2 lift came from R4 (`std → inline`), which v1 missed
entirely (0/15 top-1) and v2 catches at 10/15. See `data/r4_rerun.jsonl`
for the isolated re-run.

**Where it's weak.** R2 (chain → named) stays the hardest at 16/29 top-1,
because the router often picks R3 as the obvious surface signal; top-2
recovers it (29/29). R8 and R10 are sample-starved (n=3 each), so their
per-pattern numbers should not be read as a real estimate.

**Duration proxy.** A small ridge regression on `(loc, method_chains,
iter_combinators, difficulty)` fit on n=14 calibration points reaches
R² = 0.89, RMSE = 0.032 in log-seconds. This is a proxy fit, not a
held-out test. The number says the features carry signal, not that
rigorous calibration is done.

## Sources & credits

- **Rewrite taxonomy and prompts**: vendored from `inference-dalek`
  (`taxonomy/prompts/*.md`, refreshable via `scripts/refresh_from_dalek.py`).
  Originals belong to that project.
- **Benchmark cases**: `rewrites_v2.jsonl` is pulled from `inference-dalek`'s
  `benchmarks/` directory. `data/live_router_predictions*.jsonl` are
  predictions I generated by running this oracle's router over those cases.
- **What's new here**: the static feature extractor (`verus_oracle/features/`),
  the per-pattern specialist probes (`verus_oracle/llm/`), the score aggregator
  and bucket logic (`verus_oracle/score/`), the duration proxy regression
  (`scripts/build_calibration.py` → `data/duration_proxy.json`), the CLI,
  the FastAPI server, and the evaluation harness (`scripts/live_eval.py`).

## Status

v0.1. End-to-end stub functional; weights are seeded from prior observations and
will improve as more validated runs land. The fit procedure lives in
`scripts/build_calibration.py`.

## AI usage disclosure

Per the CS 153 AI policy:

- **Claude Opus 4.7 (via Claude Code / Anthropic API)** was used throughout
  development for code generation, debugging, and writing the LLM-router
  prompts in `taxonomy/prompts/`.
- **Runtime LLM calls.** The pipeline itself calls the Anthropic API
  (default model `claude-opus-4-7`) for the router and specialist probes;
  `--offline` disables this and falls back to static features only.
- **What I wrote vs. what was AI-assisted.** I architected the pipeline
  (router → probes → score aggregator → duration proxy) and the calibration
  design; Claude generated most of the boilerplate (CLI, FastAPI server,
  tree-sitter feature extractor) which I reviewed and edited.
- All AI-generated code was reviewed and tested before commit.
