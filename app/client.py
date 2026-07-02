from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Type, TypeVar

import ollama
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


@dataclass
class CallMetrics:
    model: str
    wall_clock_seconds: float
    time_to_first_token_seconds: float | None
    total_duration_ns: int
    load_duration_ns: int
    prompt_eval_count: int
    prompt_eval_duration_ns: int
    eval_count: int
    eval_duration_ns: int
    retries: int

    @property
    def tokens_per_second(self) -> float:
        if self.eval_duration_ns == 0:
            return 0.0
        return self.eval_count / (self.eval_duration_ns / 1e9)

    def as_dict(self) -> dict:
        return {
            "model": self.model,
            "wall_clock_seconds": self.wall_clock_seconds,
            "time_to_first_token_seconds": self.time_to_first_token_seconds,
            "total_duration_ns": self.total_duration_ns,
            "load_duration_ns": self.load_duration_ns,
            "prompt_eval_count": self.prompt_eval_count,
            "prompt_eval_duration_ns": self.prompt_eval_duration_ns,
            "eval_count": self.eval_count,
            "eval_duration_ns": self.eval_duration_ns,
            "tokens_per_second": self.tokens_per_second,
            "retries": self.retries,
        }


class SchemaValidationFailure(RuntimeError):
    pass


DEFAULT_NUM_CTX = 8192


def query_structured(
    prompt: str,
    schema: Type[T],
    model: str,
    system: str | None = None,
    temperature: float = 0.0,
    max_retries: int = 3,
    num_ctx: int = DEFAULT_NUM_CTX,
) -> tuple[T, CallMetrics]:
    """Call an Ollama model, constrain output to `schema`, validate with Pydantic,
    and retry with the validation error fed back into the conversation on failure.

    num_ctx is capped explicitly because some models advertise a very large max
    context (e.g. qwen3.5:0.8b defaults to 262144) - leaving it unset lets Ollama
    allocate/process a KV cache sized for that on every call, which on CPU-only
    inference turns a sub-second request into one that runs for many minutes."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_error: Exception | None = None
    for attempt in range(max_retries):
        start = time.perf_counter()
        ttft: float | None = None
        content_parts: list[str] = []
        final_chunk = None

        for chunk in ollama.chat(
            model=model,
            messages=messages,
            format=schema.model_json_schema(),
            options={"temperature": temperature, "num_ctx": num_ctx},
            stream=True,
        ):
            if ttft is None:
                ttft = time.perf_counter() - start
            content_parts.append(chunk["message"]["content"])
            if chunk.get("done"):
                final_chunk = chunk

        content = "".join(content_parts)
        wall_clock = time.perf_counter() - start

        try:
            parsed = schema.model_validate_json(content)
            metrics = CallMetrics(
                model=model,
                wall_clock_seconds=wall_clock,
                time_to_first_token_seconds=ttft,
                total_duration_ns=final_chunk.get("total_duration", 0) if final_chunk else 0,
                load_duration_ns=final_chunk.get("load_duration", 0) if final_chunk else 0,
                prompt_eval_count=final_chunk.get("prompt_eval_count", 0) if final_chunk else 0,
                prompt_eval_duration_ns=final_chunk.get("prompt_eval_duration", 0)
                if final_chunk
                else 0,
                eval_count=final_chunk.get("eval_count", 0) if final_chunk else 0,
                eval_duration_ns=final_chunk.get("eval_duration", 0) if final_chunk else 0,
                retries=attempt,
            )
            return parsed, metrics
        except ValidationError as e:
            last_error = e
            messages.append({"role": "assistant", "content": content})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"That response did not match the required schema: {e}. "
                        "Return valid JSON only, with no extra text."
                    ),
                }
            )

    raise SchemaValidationFailure(
        f"Failed to get a valid {schema.__name__} after {max_retries} attempts: {last_error}"
    )


def loaded_models() -> list[dict]:
    """Equivalent of `ollama ps` - which models are currently resident and their memory footprint."""
    resp = ollama.ps()
    return [m.model_dump() if hasattr(m, "model_dump") else m for m in resp.get("models", [])]
