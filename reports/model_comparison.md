# Model Comparison Report

_Fill in after running `benchmarks/run_benchmark.py` across models. See README Phase 3 for the command._

## Methodology

- Hardware:
- Models compared:
- Prompt set: `benchmarks/diffs/manifest.jsonl` (N diffs, categories: typical/edge/adversarial/out-of-domain)
- Temperature:

## Results

### Latency & throughput

| Model | Avg tokens/sec | Avg TTFT (s) | Avg total latency (s) | Resident memory |
|---|---|---|---|---|
| | | | | |

### Schema validity

| Model | Valid on first try | Valid within max_retries | Failed after retries |
|---|---|---|---|
| | | | |

### Quality (manual scoring, 0-2 per prompt: validity / field accuracy / completeness)

| Model | Typical | Edge | Adversarial | Out-of-domain |
|---|---|---|---|---|
| | | | | |

## Quantization trade-off

| Model:tag | Quantization | Memory | Tokens/sec | Schema validity |
|---|---|---|---|---|
| | | | | |

## Recommendation

_Which model for which constraint — not a single overall winner._
