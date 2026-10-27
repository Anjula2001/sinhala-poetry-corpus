import hashlib
import json

import pytest

from sinhala_corpus.convert import build_records
from sinhala_corpus.manifests import SnapshotManifest
from sinhala_corpus.parsers.sirith_maldama import EXPECTED_TITLE, parse_verses
from sinhala_corpus.reviews import ReviewDecision, ReviewFile


@pytest.fixture
def inputs():
    text = "01.<br>අ\n<br>ආ\n<br>ඇ\n<br>ඈ"
    payload = {
        "query": {
            "pages": [
                {
                    "pageid": 101231,
                    "title": EXPECTED_TITLE,
                    "revisions": [
                        {
                            "revid": 1042800,
                            "timestamp": "2023-04-07T03:29:00Z",
                            "slots": {"main": {"content": text}},
                        }
                    ],
                }
            ]
        }
    }
    raw = json.dumps(payload).encode()
    candidates = {
        "source_id": "wikisource_si",
        "page_id": 101231,
        "revision_id": 1042800,
        "snapshot_sha256": hashlib.sha256(raw).hexdigest(),
        "parser_version": 1,
        "verses": parse_verses(text),
    }
    reviews = ReviewFile(
        schema_version=1,
        source_id="wikisource_si",
        revision_id=1042800,
    )
    return raw, candidates, reviews


def test_conversion_preserves_lineage_and_safe_defaults(inputs):
    record = build_records(*inputs)[0]

    assert record.text == "අ\nආ\nඇ\nඈ"
    assert record.work_id == "wikisource_si:82432"
    assert record.provenance.source_revision_id == 1042800
    assert record.provenance.segment_number == 1
    assert record.retrieved_at is None
    assert record.review_status == "pending"
    assert record.rights.public_release_allowed is False


def test_mismatched_review_revision_is_rejected(inputs):
    raw, candidates, reviews = inputs
    reviews = reviews.model_copy(update={"revision_id": 999})

    with pytest.raises(ValueError, match="Review source or revision mismatch"):
        build_records(raw, candidates, reviews)


def test_unknown_review_verse_is_rejected(inputs):
    raw, candidates, reviews = inputs
    reviews.decisions.append(ReviewDecision(verse_number=999, status="pending"))

    with pytest.raises(ValueError, match="unknown verse"):
        build_records(raw, candidates, reviews)


def test_snapshot_checksum_mismatch_is_rejected(inputs):
    raw, candidates, reviews = inputs
    candidates["snapshot_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="provenance"):
        build_records(raw, candidates, reviews)


def test_modified_candidate_text_is_rejected(inputs):
    raw, candidates, reviews = inputs
    candidates["verses"][0]["text"] = "Edited outside the parser"

    with pytest.raises(ValueError, match="parser output"):
        build_records(raw, candidates, reviews)


@pytest.fixture
def manifest(inputs):
    raw, _, _ = inputs
    return SnapshotManifest(
        source_id="wikisource_si",
        revision_id=1042800,
        api_url="https://wikisource.org/w/api.php",
        retrieved_at="2026-10-27T14:00:00Z",
        size_bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def test_manifest_supplies_retrieval_timestamp(inputs, manifest):
    record = build_records(*inputs, manifest=manifest)[0]

    assert record.retrieved_at == manifest.retrieved_at


def test_manifest_revision_mismatch_is_rejected(inputs, manifest):
    manifest = manifest.model_copy(update={"revision_id": 999})

    with pytest.raises(ValueError, match="Manifest source or revision mismatch"):
        build_records(*inputs, manifest=manifest)


def test_manifest_source_mismatch_is_rejected(inputs, manifest):
    manifest = manifest.model_copy(update={"source_id": "another_source"})

    with pytest.raises(ValueError, match="Manifest source or revision mismatch"):
        build_records(*inputs, manifest=manifest)


def test_manifest_checksum_mismatch_is_rejected(inputs, manifest):
    manifest = manifest.model_copy(update={"sha256": "0" * 64})

    with pytest.raises(ValueError, match="checksum"):
        build_records(*inputs, manifest=manifest)
