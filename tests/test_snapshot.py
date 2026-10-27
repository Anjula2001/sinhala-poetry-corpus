import hashlib
import json

import httpx
import pytest

from sinhala_corpus.collectors.snapshot import fetch_revision, save_snapshot


def revision_response(revision_id):
    return {
        "query": {
            "pages": [
                {
                    "pageid": 42,
                    "revisions": [
                        {
                            "revid": revision_id,
                            "slots": {
                                "main": {
                                    "contentmodel": "wikitext",
                                    "content": "Test verse\n\nSecond stanza",
                                }
                            },
                        }
                    ],
                }
            ]
        }
    }


def test_original_response_bytes_are_preserved():
    raw = json.dumps(revision_response(123), indent=2).encode()

    def handler(request):
        assert request.url.params["revids"] == "123"
        return httpx.Response(200, content=raw)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_revision(client, "https://example.org/api.php", 123)

    assert result == raw


def test_wrong_revision_is_rejected():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=revision_response(999))
    )

    with (
        httpx.Client(transport=transport) as client,
        pytest.raises(ValueError, match="does not match"),
    ):
        fetch_revision(client, "https://example.org/api.php", 123)


def test_snapshot_is_saved_with_checksum(tmp_path):
    path = tmp_path / "raw" / "revision-123.json"
    content = b'{"example": true}'

    checksum = save_snapshot(path, content)

    assert path.read_bytes() == content
    assert checksum == hashlib.sha256(content).hexdigest()


def test_existing_snapshot_is_not_overwritten(tmp_path):
    path = tmp_path / "revision-123.json"
    path.write_bytes(b"original")

    with pytest.raises(FileExistsError):
        save_snapshot(path, b"replacement")

    assert path.read_bytes() == b"original"
