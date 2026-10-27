import pytest
from pydantic import ValidationError

from sinhala_corpus.schema import CorpusRecord


@pytest.fixture
def record_data():
    return {
        "id": "test:001",
        "text": "පළමු පේළිය\n\nදෙවන පේළිය",
        "type": "poem",
        "source_id": "test",
        "source_record_id": "001",
        "source_url": "https://example.org/poems/001",
        "retrieved_at": "2026-10-27T14:00:00Z",
    }


def test_text_layout_is_preserved(record_data):
    record = CorpusRecord.model_validate(record_data)
    assert record.text == record_data["text"]
    assert record.review_status == "pending"
    assert record.rights.public_release_allowed is False


def test_blank_text_is_rejected(record_data):
    record_data["text"] = " \n\t "

    with pytest.raises(ValidationError, match="whitespace"):
        CorpusRecord.model_validate(record_data)


def test_timestamp_requires_timezone(record_data):
    record_data["retrieved_at"] = "2026-10-27T14:00:00"

    with pytest.raises(ValidationError):
        CorpusRecord.model_validate(record_data)


def test_unknown_rights_cannot_allow_release(record_data):
    record_data["rights"] = {"public_release_allowed": True}

    with pytest.raises(ValidationError, match="known rights basis"):
        CorpusRecord.model_validate(record_data)


def test_open_license_release_requires_license(record_data):
    record_data["rights"] = {
        "basis": "open_license",
        "evidence_urls": ["https://example.org/license"],
        "public_release_allowed": True,
    }

    with pytest.raises(ValidationError, match="license identifier"):
        CorpusRecord.model_validate(record_data)


def test_record_round_trips_through_json(record_data):
    record = CorpusRecord.model_validate(record_data)
    restored = CorpusRecord.model_validate_json(record.model_dump_json())
    assert restored == record
