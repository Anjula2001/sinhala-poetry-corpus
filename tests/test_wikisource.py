import httpx
import pytest

from sinhala_corpus.collectors.wikisource import fetch_metadata


def test_metadata_is_extracted():
    def handler(request):
        assert request.url.params["titles"] == "Test poem"
        assert request.url.params["rvprop"] == "ids|timestamp"
        return httpx.Response(
            200,
            json={
                "query": {
                    "pages": [
                        {
                            "pageid": 42,
                            "title": "Test poem",
                            "fullurl": "https://example.org/wiki/Test_poem",
                            "revisions": [
                                {
                                    "revid": 123,
                                    "timestamp": "2026-10-27T14:00:00Z",
                                }
                            ],
                        }
                    ]
                }
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        metadata = fetch_metadata(client, "https://example.org/api.php", "Test poem")

    assert metadata.page_id == 42
    assert metadata.revision_id == 123
    assert metadata.title == "Test poem"
    assert metadata.revision_timestamp.tzinfo is not None


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {"query": {"pages": [{"title": "Missing", "missing": True}]}},
            "Page not found",
        ),
        (
            {"error": {"code": "maxlag"}},
            "MediaWiki API error: maxlag",
        ),
    ],
)
def test_invalid_api_results_are_rejected(payload, message):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    with (
        httpx.Client(transport=transport) as client,
        pytest.raises(ValueError, match=message),
    ):
        fetch_metadata(client, "https://example.org/api.php", "Missing")
