import hashlib

import pytest
from pydantic import ValidationError

from sinhala_corpus.manifests import (
    SnapshotManifest,
    load_manifest,
    write_manifest,
)


@pytest.fixture
def snapshot(tmp_path):
    path = tmp_path / "revision-123.json"
    raw = b'{"example": true}'
    path.write_bytes(raw)

    manifest = SnapshotManifest(
        source_id="wikisource_si",
        revision_id=123,
        api_url="https://example.org/api.php",
        retrieved_at="2026-10-27T14:00:00Z",
        size_bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
    )
    return path, manifest


def test_manifest_round_trip(snapshot):
    path, manifest = snapshot
    manifest_path = write_manifest(path, manifest)

    assert manifest_path.name == "revision-123.meta.json"
    assert load_manifest(path) == manifest


def test_changed_snapshot_is_detected(snapshot):
    path, manifest = snapshot
    write_manifest(path, manifest)

    # Same length, different content: checksum must catch this.
    path.write_bytes(b'{"example": True}')

    with pytest.raises(ValueError, match="checksum"):
        load_manifest(path)


def test_existing_manifest_is_not_overwritten(snapshot):
    path, manifest = snapshot
    write_manifest(path, manifest)

    with pytest.raises(FileExistsError):
        write_manifest(path, manifest)


def test_retrieval_timestamp_requires_timezone():
    with pytest.raises(ValidationError):
        SnapshotManifest(
            source_id="wikisource_si",
            revision_id=123,
            api_url="https://example.org/api.php",
            retrieved_at="2026-10-27T14:00:00",
            size_bytes=10,
            sha256="0" * 64,
        )
