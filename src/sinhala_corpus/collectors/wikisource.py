import argparse
import sys
from pathlib import Path

import httpx
from pydantic import AwareDatetime, BaseModel, HttpUrl

from sinhala_corpus.sources import load_sources


class PageMetadata(BaseModel):
    page_id: int
    title: str
    revision_id: int
    revision_timestamp: AwareDatetime
    source_url: HttpUrl


def fetch_metadata(
    client: httpx.Client,
    api_url: str,
    title: str,
) -> PageMetadata:
    response = client.get(
        api_url,
        params={
            "action": "query",
            "prop": "info|revisions",
            "inprop": "url",
            "rvprop": "ids|timestamp",
            "rvlimit": 1,
            "titles": title,
            "redirects": 1,
            "format": "json",
            "formatversion": 2,
            "maxlag": 5,
        },
    )
    response.raise_for_status()
    payload = response.json()

    if "error" in payload:
        error = payload["error"]
        raise ValueError(f"MediaWiki API error: {error.get('code', 'unknown')}")

    pages = payload.get("query", {}).get("pages", [])
    if len(pages) != 1:
        raise ValueError("Expected exactly one page.")

    page = pages[0]
    if "missing" in page or "invalid" in page:
        raise ValueError(f"Page not found or invalid: {title}")

    revisions = page.get("revisions", [])
    if not revisions:
        raise ValueError("Page has no accessible revision.")

    revision = revisions[0]
    return PageMetadata.model_validate(
        {
            "page_id": page.get("pageid"),
            "title": page.get("title"),
            "revision_id": revision.get("revid"),
            "revision_timestamp": revision.get("timestamp"),
            "source_url": page.get("fullurl"),
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a Wikisource page.")
    parser.add_argument("--title", required=True)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/sources.yaml"),
    )
    args = parser.parse_args()

    try:
        registry = load_sources(args.config)
        source = next(
            (item for item in registry.sources if item.id == "wikisource_si"),
            None,
        )
        if source is None or not source.enabled or source.base_url is None:
            raise ValueError("Wikisource source must be configured and enabled.")

        with httpx.Client(
            timeout=registry.collection_defaults.timeout_seconds,
            headers={
                "User-Agent": (
                    "SinhalaPoetryCorpus/0.1 "
                    "(https://github.com/Anjula2001/sinhala-poetry-corpus)"
                ),
                "Accept": "application/json",
            },
        ) as client:
            metadata = fetch_metadata(
                client,
                str(source.base_url),
                args.title,
            )

    except (httpx.HTTPError, OSError, ValueError) as exc:
        print(f"Metadata fetch failed: {exc}", file=sys.stderr)
        return 1

    print(metadata.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
