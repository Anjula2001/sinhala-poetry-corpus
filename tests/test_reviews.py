import pytest
from pydantic import ValidationError

from sinhala_corpus.reviews import ReviewDecision, ReviewFile


def test_pending_review_does_not_require_reviewer():
    decision = ReviewDecision(verse_number=49, status="pending")
    assert decision.reviewed_at is None


def test_approval_requires_reviewer():
    with pytest.raises(ValidationError, match="require a reviewer"):
        ReviewDecision(verse_number=1, status="approved")


def test_approval_requires_timestamp():
    with pytest.raises(ValidationError, match="review timestamp"):
        ReviewDecision(
            verse_number=1,
            status="approved",
            reviewer="Test reviewer",
        )


def test_rejection_requires_reason():
    with pytest.raises(ValidationError, match="require a reason"):
        ReviewDecision(
            verse_number=49,
            status="rejected",
            reviewer="Test reviewer",
            reviewed_at="2026-10-27T14:00:00Z",
        )


def test_duplicate_decisions_are_rejected():
    with pytest.raises(ValidationError, match="only one review decision"):
        ReviewFile.model_validate(
            {
                "schema_version": 1,
                "source_id": "wikisource_si",
                "revision_id": 1042800,
                "decisions": [
                    {"verse_number": 49, "status": "pending"},
                    {"verse_number": 49, "status": "pending"},
                ],
            }
        )
