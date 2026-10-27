import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

from sinhala_corpus.manifests import SnapshotManifest, write_manifest
from sinhala_corpus.sources import load_sources


def fetch_revision(
    client: httpx.Client,
    api_url: str,
    revision_id: int,
) -> bytes:
    response = client.get(
        api_url,
        params={
            "action": "query",
            "prop": "revisions",
            "revids": revision_id,
            "rvprop": "ids|timestamp|content|contentmodel",
            "rvslots": "main",
            "format": "json",
            "formatversion": 2,
            "maxlag": 5,
        },
    )
    response.raise_for_status()
    payload = response.json()

    if "error" in payload:
        code = payload["error"].get("code", "unknown")
        raise ValueError(f"MediaWiki API error: {code}")

    pages = payload.get("query", {}).get("pages", [])
    if len(pages) != 1:
        raise ValueError("Expected exactly one page.")

    page = pages[0]
    if "missing" in page or "invalid" in page:
        raise ValueError("Requested page is missing or invalid.")

    revisions = page.get("revisions", [])
    if len(revisions) != 1:
        raise ValueError("Expected exactly one accessible revision.")

    revision = revisions[0]
    if revision.get("revid") != revision_id:
        raise ValueError("Returned revision does not match the requested ID.")

    slot = revision.get("slots", {}).get("main", {})
    if slot.get("contentmodel") != "wikitext":
        raise ValueError("Expected wikitext content.")

    content = slot.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Revision content is missing or empty.")

    # Preserve the original JSON response bytes.
    return response.content


def save_snapshot(path: Path, content: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)

    # Exclusive creation prevents overwriting an existing snapshot.
    with path.open("xb") as file:
        file.write(content)

    return hashlib.sha256(content).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Save a raw Wikisource revision.")
    parser.add_argument("--revision", required=True, type=int)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/sources.yaml"),
    )
    args = parser.parse_args()

    if args.revision <= 0:
        parser.error("--revision must be positive")

    output = Path("data/raw/wikisource_si") / f"revision-{args.revision}.json"

    try:
        if output.exists():
            raise FileExistsError(f"Snapshot already exists: {output}")

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
            content = fetch_revision(client, str(source.base_url), args.revision)

        retrieved_at = datetime.now(UTC)
        checksum = save_snapshot(output, content)

        manifest = SnapshotManifest(
            source_id=source.id,
            revision_id=args.revision,
            api_url=source.base_url,
            retrieved_at=retrieved_at,
            size_bytes=len(content),
            sha256=checksum,
        )
        manifest_path = write_manifest(output, manifest)

    except (httpx.HTTPError, OSError, ValueError) as exc:
        print(f"Snapshot failed: {exc}", file=sys.stderr)
        return 1

    print(f"Saved: {output}")
    print(f"Bytes: {len(content)}")
    print(f"SHA-256: {checksum}")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
