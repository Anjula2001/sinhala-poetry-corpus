import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import sinhala_corpus.upload as upload
from sinhala_corpus.manifests import SnapshotManifest, write_manifest
from sinhala_corpus.staging import STAGING_REPO


def make_api(*, private=True, existing=None):
    return SimpleNamespace(
        repo_info=Mock(
            return_value=SimpleNamespace(
                id=STAGING_REPO,
                private=private,
                sha="a" * 40,
            )
        ),
        list_repo_files=Mock(return_value=existing or []),
        create_commit=Mock(return_value=SimpleNamespace(oid="b" * 40)),
    )


def test_bundle_only_includes_selected_files(tmp_path):
    for relative in upload.BUNDLE_FILES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if not relative.endswith(".meta.json"):
            path.write_bytes(b"fixture")

    snapshot = tmp_path / upload.BUNDLE_FILES[0]
    checksum = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    write_manifest(
        snapshot,
        SnapshotManifest(
            source_id="wikisource_si",
            revision_id=1042800,
            api_url="https://example.org/api.php",
            retrieved_at="2026-10-28T14:00:00Z",
            size_bytes=len(snapshot.read_bytes()),
            sha256=checksum,
        ),
    )

    (tmp_path / upload.BUNDLE_FILES[-1]).write_text(
        json.dumps(
            {
                "source_id": "wikisource_si",
                "revision_id": 1042800,
                "snapshot_sha256": checksum,
                "manifest_status": "verified",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text("PRIVATE_VALUE=test", encoding="utf-8")

    files = upload.prepare_bundle(tmp_path)

    assert set(files) == set(upload.BUNDLE_FILES)
    assert ".env" not in files


def test_public_repository_prevents_upload(tmp_path):
    api = make_api(private=False)

    with pytest.raises(ValueError, match="must be private"):
        upload.upload_bundle(
            api,
            root=tmp_path,
            run_id="123",
            run_attempt="1",
            code_commit="c" * 40,
        )

    api.create_commit.assert_not_called()


def test_existing_run_is_not_overwritten(tmp_path, monkeypatch):
    api = make_api(existing=["runs/123/1/run.json"])
    monkeypatch.setattr(upload, "prepare_bundle", lambda root: {"test": b"data"})

    with pytest.raises(ValueError, match="already exists"):
        upload.upload_bundle(
            api,
            root=tmp_path,
            run_id="123",
            run_attempt="1",
            code_commit="c" * 40,
        )

    api.create_commit.assert_not_called()


def test_upload_records_code_commit_and_uses_parent_guard(tmp_path, monkeypatch):
    api = make_api()
    monkeypatch.setattr(upload, "prepare_bundle", lambda root: {"test": b"data"})

    commit = upload.upload_bundle(
        api,
        root=tmp_path,
        run_id="123",
        run_attempt="1",
        code_commit="c" * 40,
    )

    assert commit == "b" * 40
    kwargs = api.create_commit.call_args.kwargs
    assert kwargs["parent_commit"] == "a" * 40
    operations = kwargs["operations"]
    assert {operation.path_in_repo for operation in operations} == {
        "runs/123/1/test",
        "runs/123/1/run.json",
    }
    metadata = next(
        operation.path_or_fileobj
        for operation in operations
        if operation.path_in_repo.endswith("/run.json")
    )
    assert json.loads(metadata)["code_commit"] == "c" * 40
