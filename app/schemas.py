from typing import Literal

from pydantic import BaseModel, Field


class CodeReview(BaseModel):
    change_type: Literal[
        "feature", "bugfix", "refactor", "test", "docs", "chore", "config", "other"
    ]
    summary: str = Field(description="One or two sentence summary of what the diff does")
    risk_level: Literal["low", "medium", "high"]
    suggested_tests: list[str] = Field(
        default_factory=list,
        description="Concrete test cases or scenarios that should cover this change",
    )
