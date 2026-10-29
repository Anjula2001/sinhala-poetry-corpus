import hashlib
import json

import pytest

from sinhala_corpus.restore import verify_bundle
from sinhala_corpus.upload import BUNDLE_FILES


@pytest.fixture
def bundle():
    files = {name: b"fixture" for name in BUNDLE_FILES}
    metadata = {
        "bundle_version": 1,
        "github_repository": "Anjula2001/sinhala-poetry-corpus",
        "github_run_id": "123",
        "github_run_attempt": "1",
        "code_commit": "c" * 40,
        "files": {
            name: {
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            for name, content in files.items()
        },
    }
    files["run.json"] = json.dumps(metadata).encode()
    return files


def check(files):
    return verify_bundle(
        files,
        run_id="123",
        run_attempt="1",
        code_commit="c" * 40,
    )


def test_complete_bundle_verifies(bundle):
    assert check(bundle)["files_verified"] == 6


def test_same_size_corruption_is_detected(bundle):
    bundle[BUNDLE_FILES[0]] = b"damaged"

    with pytest.raises(ValueError, match="Checksum mismatch"):
        check(bundle)


def test_missing_file_is_rejected(bundle):
    del bundle[BUNDLE_FILES[0]]

    with pytest.raises(ValueError, match="missing or unexpected"):
        check(bundle)


def test_unexpected_manifest_path_is_rejected(bundle):
    metadata = json.loads(bundle["run.json"])
    metadata["files"]["../../unexpected"] = {}
    bundle["run.json"] = json.dumps(metadata).encode()

    with pytest.raises(ValueError, match="unexpected file paths"):
        check(bundle)


def test_wrong_code_commit_is_rejected(bundle):
    metadata = json.loads(bundle["run.json"])
    metadata["code_commit"] = "d" * 40
    bundle["run.json"] = json.dumps(metadata).encode()

    with pytest.raises(ValueError, match="expected run"):
        check(bundle)
