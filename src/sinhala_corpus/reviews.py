from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verse_number: int = Field(gt=0, strict=True)
    status: Literal["pending", "approved", "rejected"]
    reviewer: str | None = None
    reviewed_at: AwareDatetime | None = None
    notes: str = ""

    @model_validator(mode="after")
    def validate_completed_review(self) -> Self:
        if self.status != "pending":
            if not self.reviewer or not self.reviewer.strip():
                raise ValueError("Completed reviews require a reviewer.")
            if self.reviewed_at is None:
                raise ValueError("Completed reviews require a review timestamp.")

        if self.status == "rejected" and not self.notes.strip():
            raise ValueError("Rejected verses require a reason.")

        return self


class ReviewFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    source_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    revision_id: int = Field(gt=0, strict=True)
    decisions: list[ReviewDecision] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_decisions(self) -> Self:
        numbers = [decision.verse_number for decision in self.decisions]
        if len(numbers) != len(set(numbers)):
            raise ValueError("Each verse may have only one review decision.")
        return self


def load_reviews(path: Path) -> ReviewFile:
    with path.open(encoding="utf-8") as file:
        payload = yaml.safe_load(file)
    return ReviewFile.model_validate(payload)
