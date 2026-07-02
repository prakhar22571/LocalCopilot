from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.client import SchemaValidationFailure, loaded_models, query_structured  # noqa: E402
from app.prompts import REVIEW_SYSTEM_PROMPT, build_review_prompt  # noqa: E402
from app.schemas import CodeReview  # noqa: E402

DIFFS_DIR = Path(__file__).parent / "diffs"
RESULTS_DIR = Path(__file__).parent / "results"
# qwen3.5:0.8b is excluded by default - it hangs indefinitely on this machine even on a
# trivial unconstrained prompt sent directly via `ollama run`. Re-pull it and add it back
# with --models once confirmed working.
DEFAULT_MODELS = ["mistral:7b", "granite4:3b"]


def load_manifest() -> list[dict]:
    manifest_path = DIFFS_DIR / "manifest.jsonl"
    with open(manifest_path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def memory_for_model(model: str) -> int | None:
    for m in loaded_models():
        if m.get("model") == model or m.get("name") == model:
            return m.get("size")
    return None


def run_sweep(models: list[str], temperatures: list[float], repeats: int) -> list[dict]:
    manifest = load_manifest()
    rows: list[dict] = []
    total = len(models) * len(manifest) * len(temperatures) * repeats
    done = 0

    for model in models:
        for entry in manifest:
            diff_text = (DIFFS_DIR / entry["file"]).read_text(encoding="utf-8")
            prompt = build_review_prompt(diff_text)
            for temperature in temperatures:
                for rep in range(repeats):
                    done += 1
                    row = {
                        "model": model,
                        "diff_id": entry["id"],
                        "category": entry["category"],
                        "temperature": temperature,
                        "repeat": rep,
                    }
                    print(f"[{done}/{total}] {model} | {entry['id']} | T={temperature} | rep={rep}", file=sys.stderr)
                    start = time.perf_counter()
                    try:
                        review, metrics = query_structured(
                            prompt=prompt,
                            schema=CodeReview,
                            model=model,
                            system=REVIEW_SYSTEM_PROMPT,
                            temperature=temperature,
                        )
                        row["schema_valid"] = True
                        row["error"] = None
                        row["change_type"] = review.change_type
                        row["risk_level"] = review.risk_level
                        row["suggested_tests_count"] = len(review.suggested_tests)
                        row.update(metrics.as_dict())
                    except SchemaValidationFailure as e:
                        row["schema_valid"] = False
                        row["error"] = str(e)
                        row["wall_clock_seconds"] = time.perf_counter() - start
                    row["resident_memory_bytes"] = memory_for_model(model)
                    rows.append(row)
    return rows


def write_results(rows: list[dict], tag: str) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    jsonl_path = RESULTS_DIR / f"{tag}.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

    csv_path = RESULTS_DIR / f"{tag}.csv"
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return csv_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep models x diffs x temperatures and log metrics.")
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS), help="Comma-separated Ollama model tags")
    parser.add_argument("--temperatures", default="0.0", help="Comma-separated temperature values")
    parser.add_argument("--repeats", type=int, default=1, help="Repeats per (model, diff, temperature) combo")
    parser.add_argument("--tag", default=None, help="Output file name stem (default: timestamp)")
    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    temperatures = [float(t.strip()) for t in args.temperatures.split(",") if t.strip()]
    tag = args.tag or time.strftime("run_%Y%m%d_%H%M%S")

    rows = run_sweep(models, temperatures, args.repeats)
    out_path = write_results(rows, tag)
    print(f"Wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
