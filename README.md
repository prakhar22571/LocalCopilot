# Local Copilot — Offline Code Review Assistant

A fully offline code-review assistant built on a local Small Language Model (SLM). Feed it a
git diff; it returns a structured `{change_type, summary, risk_level, suggested_tests}` review.
No code ever leaves the machine.

Built in three phases: get it running and measured, make it reliable and structured, then
compare models systematically.

## Setup

Requires [Ollama](https://ollama.com) running locally with at least one model pulled:

```bash
ollama pull granite4:3b
ollama pull mistral:7b
ollama pull qwen3.5:0.8b
```

Then set up the Python environment:

```bash
python -m venv .venv
.venv/Scripts/activate        # .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
```

## Usage

### CLI

```bash
# Review the diff between HEAD and the working tree
python -m app.cli --git-ref HEAD

# Review a saved diff file
python -m app.cli --diff-file some_change.diff

# Pipe a diff in directly
git diff | python -m app.cli

# Pick a model, print performance metrics to stderr
python -m app.cli --diff-file some_change.diff --model mistral:7b --metrics
```

### API

```bash
uvicorn app.api:app --reload
```

```bash
curl -X POST http://localhost:8000/review \
  -H "Content-Type: application/json" \
  -d '{"diff": "diff --git a/x.py b/x.py\n...", "model": "granite4:3b"}'
```

## Project structure

```
app/
  schemas.py        Pydantic schema for a review (CodeReview)
  prompts.py         System prompt + diff prompt template
  client.py           Ollama call, JSON-schema constraint, validate/retry loop, metrics capture
  cli.py                Command-line entry point
  api.py                FastAPI wrapper around the same client logic
benchmarks/
  diffs/              Seed test diffs (typical/edge/adversarial/out-of-domain), manifest.jsonl
  run_benchmark.py    Sweeps models x diffs x temperatures, logs metrics to benchmarks/results/
reports/
  model_comparison.md  Write-up of Phase 3 findings (fill in after running the sweep)
```

## Phase 1 — Foundations & benchmarking

`app/client.py`'s `query_structured()` streams every Ollama call so time-to-first-token is a
real measurement rather than collapsing into total latency, and pulls `total_duration`,
`load_duration`, `prompt_eval_count/duration`, and `eval_count/duration` straight from Ollama's
own response rather than hand-rolled timers. `tokens_per_second` is derived from
`eval_count / eval_duration`.

Run a single call with `--metrics` to see the numbers:

```bash
python -m app.cli --diff-file benchmarks/diffs/typical_01_feature.diff --metrics
```

Note that the first call to a model pays a cold-start `load_duration` cost; run twice back to
back if you want to see warm vs. cold behavior separately, and control it explicitly via
Ollama's `keep_alive` if you need the model resident between runs.

## Phase 2 — Structure & determinism

- **Schema**: `app/schemas.py` defines `CodeReview` as the single source of truth for output shape.
- **Constrained decoding + validation**: `query_structured()` passes `schema.model_json_schema()`
  as Ollama's `format` parameter (constrains generation), then validates the result with
  Pydantic (catches anything the grammar constraint doesn't, like out-of-range values).
- **Retry loop**: on a `ValidationError`, the raw invalid output and the specific error message
  are appended back into the conversation and the model is asked to correct itself, up to
  `--max-retries` (default 3). See `SchemaValidationFailure` for the terminal failure case.
- **Temperature study**: use the benchmark sweep to run the same diff N times at temperature 0
  vs. 0.7 and compare schema-validity rate and field-level agreement across runs:

  ```bash
  python benchmarks/run_benchmark.py --models granite4:3b --temperatures 0.0,0.7 --repeats 15 --tag temp_study
  ```

  Then look at `benchmarks/results/temp_study.csv` — group by `temperature` and compare
  `schema_valid` rate and how much `change_type`/`risk_level` vary across repeats of the same
  diff.

## Phase 3 — Model comparison study

The seed set in `benchmarks/diffs/` has 13 diffs across four categories (typical, edge,
adversarial, out-of-domain) — enough to smoke-test the pipeline. Expand it to 30-50 before
drawing real conclusions; `manifest.jsonl` documents what each existing diff is designed to
probe (e.g. `adversarial_01_prompt_injection.diff` tests whether an in-diff comment can talk
the model into misreporting risk on a real security issue).

Run the full comparison:

```bash
python benchmarks/run_benchmark.py --models mistral:7b,granite4:3b --temperatures 0.0
```

> `qwen3.5:0.8b` currently hangs indefinitely on this machine even on a trivial unconstrained
> prompt sent directly via `ollama run` (not an issue in this app's code — see git history around
> the `num_ctx` fix in `client.py` for the debugging trail). Re-pull it (`ollama rm qwen3.5:0.8b
> && ollama pull qwen3.5:0.8b`) before including it in the comparison.

This writes `benchmarks/results/<tag>.csv` with, per run: model, diff category, latency,
tokens/sec, TTFT, schema validity, resident memory (via `ollama ps`, pulled by
`loaded_models()` in `client.py`), and the model's actual `change_type`/`risk_level` output for
manual quality scoring.

**Quantization**: pull a second tag of your strongest model at a different quantization level
(e.g. `ollama pull mistral:7b-instruct-q4_K_M` vs `q5_K_M`) and add both tags to `--models` to
compare memory/speed/schema-validity side by side.

Write up the findings in `reports/model_comparison.md` — methodology, a results table per
metric, and a recommendation tied to a specific constraint (e.g. "optimize for latency" vs.
"optimize for risk-detection quality") rather than a single overall winner.
