import httpx
import pytest
from pydantic import ValidationError

from sinhala_corpus.api_probe import fetch_stats


def test_valid_stats_response():
    def handler(request):
        assert request.method == "GET"
        assert str(request.url) == "https://example.org/api/stats"
        return httpx.Response(200, json={"songs": 10, "artists": 5})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        stats = fetch_stats(client, "https://example.org/api/")

    assert stats.songs == 10
    assert stats.artists == 5


def test_server_error_is_not_treated_as_success():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(503, text="Unavailable")
    )

    with (
        httpx.Client(transport=transport) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        fetch_stats(client, "https://example.org/api")


def test_invalid_stats_are_rejected():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"songs": -1, "artists": 5})
    )

    with (
        httpx.Client(transport=transport) as client,
        pytest.raises(ValidationError),
    ):
        fetch_stats(client, "https://example.org/api")
