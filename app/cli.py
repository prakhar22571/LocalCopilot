from __future__ import annotations

import argparse
import json
import subprocess
import sys

from app.client import DEFAULT_NUM_CTX, SchemaValidationFailure, query_structured
from app.prompts import REVIEW_SYSTEM_PROMPT, build_review_prompt
from app.schemas import CodeReview

DEFAULT_MODEL = "granite4:3b"


def read_diff(args: argparse.Namespace) -> str:
    if args.diff_file:
        with open(args.diff_file, "r", encoding="utf-8") as f:
            return f.read()
    if args.git_ref:
        result = subprocess.run(
            ["git", "diff", args.git_ref],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise SystemExit("No diff provided. Use --diff-file, --git-ref, or pipe a diff via stdin.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Review a git diff with a local SLM.")
    parser.add_argument("--diff-file", help="Path to a file containing a unified diff")
    parser.add_argument("--git-ref", help="Git ref to diff against, e.g. HEAD~1 or --staged")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama model tag (default: {DEFAULT_MODEL})")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--num-ctx", type=int, default=DEFAULT_NUM_CTX, help=f"Context window size (default: {DEFAULT_NUM_CTX})")
    parser.add_argument("--metrics", action="store_true", help="Print performance metrics to stderr")
    args = parser.parse_args()

    diff = read_diff(args)
    prompt = build_review_prompt(diff)

    try:
        review, metrics = query_structured(
            prompt=prompt,
            schema=CodeReview,
            model=args.model,
            system=REVIEW_SYSTEM_PROMPT,
            temperature=args.temperature,
            max_retries=args.max_retries,
            num_ctx=args.num_ctx,
        )
    except SchemaValidationFailure as e:
        print(f"error: {e}", file=sys.stderr)
        raise SystemExit(1)

    print(review.model_dump_json(indent=2))
    if args.metrics:
        print(json.dumps(metrics.as_dict(), indent=2), file=sys.stderr)


if __name__ == "__main__":
    main()
