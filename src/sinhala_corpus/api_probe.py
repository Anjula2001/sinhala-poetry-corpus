import argparse
import sys
from pathlib import Path

import httpx
from pydantic import BaseModel, Field

from sinhala_corpus.sources import load_sources


class ApiStats(BaseModel):
    songs: int = Field(ge=0, strict=True)
    artists: int = Field(ge=0, strict=True)


def fetch_stats(client: httpx.Client, base_url: str) -> ApiStats:
    url = f"{base_url.rstrip('/')}/stats"
    response = client.get(url)
    response.raise_for_status()
    return ApiStats.model_validate(response.json())


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Mathaka API connectivity.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/sources.yaml"),
    )
    args = parser.parse_args()

    try:
        registry = load_sources(args.config)
        source = next(
            (item for item in registry.sources if item.id == "mathaka"),
            None,
        )

        if source is None or source.base_url is None:
            raise ValueError("Mathaka source and base_url must be configured.")

        with httpx.Client(
            timeout=registry.collection_defaults.timeout_seconds,
            follow_redirects=False,
            headers={
                "User-Agent": "sinhala-poetry-corpus/0.1 (API connectivity probe)",
                "Accept": "application/json",
            },
        ) as client:
            stats = fetch_stats(client, str(source.base_url))

    except httpx.HTTPStatusError as exc:
        print(
            f"API check failed: HTTP {exc.response.status_code}",
            file=sys.stderr,
        )
        return 1
    except httpx.RequestError as exc:
        print(
            f"Connection failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1
    except (OSError, ValueError) as exc:
        print(f"Configuration or response error: {exc}", file=sys.stderr)
        return 1

    print("Mathaka stats endpoint: OK")
    print(f"Songs reported: {stats.songs}")
    print(f"Artists reported: {stats.artists}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
