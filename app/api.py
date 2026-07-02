from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.client import DEFAULT_NUM_CTX, SchemaValidationFailure, query_structured
from app.prompts import REVIEW_SYSTEM_PROMPT, build_review_prompt
from app.schemas import CodeReview

app = FastAPI(title="Local Copilot - Code Review Assistant")


class ReviewRequest(BaseModel):
    diff: str
    model: str = "granite4:3b"
    temperature: float = 0.0
    max_retries: int = 3
    num_ctx: int = DEFAULT_NUM_CTX


class ReviewResponse(BaseModel):
    review: CodeReview
    metrics: dict


@app.post("/review", response_model=ReviewResponse)
def review_diff(req: ReviewRequest) -> ReviewResponse:
    prompt = build_review_prompt(req.diff)
    try:
        review, metrics = query_structured(
            prompt=prompt,
            schema=CodeReview,
            model=req.model,
            system=REVIEW_SYSTEM_PROMPT,
            temperature=req.temperature,
            max_retries=req.max_retries,
            num_ctx=req.num_ctx,
        )
    except SchemaValidationFailure as e:
        raise HTTPException(status_code=422, detail=str(e))

    return ReviewResponse(review=review, metrics=metrics.as_dict())


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
