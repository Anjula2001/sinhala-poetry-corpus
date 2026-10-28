import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import httpx
import yaml
from pydantic import BaseModel, ConfigDict, Field

from sinhala_corpus.audit import audit_layout
from sinhala_corpus.collectors.snapshot import fetch_revision, save_snapshot
from sinhala_corpus.convert import build_records
from sinhala_corpus.manifests import (
    SnapshotManifest,
    load_manifest,
    write_manifest,
)
from sinhala_corpus.parsers.sirith_maldama import EXPECTED_TITLE, parse_verses
from sinhala_corpus.reviews import load_reviews
from sinhala_corpus.sources import load_sources


class PipelineConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    name: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    source_id: Literal["wikisource_si"]
    revision_id: Literal[1042800]
    source_config: Path
    review_file: Path


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run_pipeline(config: PipelineConfig) -> dict:
    registry = load_sources(config.source_config)
    reviews = load_reviews(config.review_file)

    if (
        reviews.source_id != config.source_id
        or reviews.revision_id != config.revision_id
    ):
        raise ValueError("Pipeline and review source/revision must match.")

    source = next(
        (item for item in registry.sources if item.id == config.source_id),
        None,
    )
    if source is None or not source.enabled or source.base_url is None:
        raise ValueError("Pipeline source must be configured and enabled.")

    snapshot = (
        Path("data/raw") / config.source_id / f"revision-{config.revision_id}.json"
    )

    if not snapshot.exists():
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
            raw = fetch_revision(
                client,
                str(source.base_url),
                config.revision_id,
            )

        retrieved_at = datetime.now(UTC)
        checksum = save_snapshot(snapshot, raw)
        write_manifest(
            snapshot,
            SnapshotManifest(
                source_id=config.source_id,
                revision_id=config.revision_id,
                api_url=source.base_url,
                retrieved_at=retrieved_at,
                size_bytes=len(raw),
                sha256=checksum,
            ),
        )

    # Reuse existing snapshots without overwriting them.
    raw = snapshot.read_bytes()
    manifest = (
        load_manifest(snapshot) if snapshot.with_suffix(".meta.json").exists() else None
    )

    payload = json.loads(raw)
    page = payload["query"]["pages"][0]
    revision = page["revisions"][0]

    if page["title"] != EXPECTED_TITLE or revision["revid"] != config.revision_id:
        raise ValueError("Snapshot does not match the supported work/revision.")

    text = revision["slots"]["main"]["content"]
    checksum = hashlib.sha256(raw).hexdigest()
    audit = audit_layout(text)

    audit_path = Path("artifacts/audits") / f"{config.name}.json"
    write_json(
        audit_path,
        {
            "audit_version": 1,
            "source_id": config.source_id,
            "revision_id": config.revision_id,
            "snapshot_sha256": checksum,
            **audit,
        },
    )

    if audit["layout_status"] == "requires_review":
        raise ValueError(f"Layout requires review. See {audit_path}")

    verses = parse_verses(text)
    candidates = {
        "parser_version": 1,
        "source_id": config.source_id,
        "page_id": page["pageid"],
        "title": page["title"],
        "revision_id": config.revision_id,
        "snapshot_sha256": checksum,
        "public_release_allowed": False,
        "verse_count": len(verses),
        "flagged_verse_numbers": [
            verse["verse_number"] for verse in verses if verse["quality_flags"]
        ],
        "verses": verses,
    }

    records = build_records(raw, candidates, reviews, manifest=manifest)

    candidates_path = Path("data/processed") / f"{config.name}-candidates.json"
    records_path = Path("data/processed") / f"{config.name}-records.jsonl"

    write_json(candidates_path, candidates)
    records_path.write_text(
        "".join(record.model_dump_json() + "\n" for record in records),
        encoding="utf-8",
    )

    summary = {
        "pipeline_version": 1,
        "source_id": config.source_id,
        "revision_id": config.revision_id,
        "snapshot_sha256": checksum,
        "manifest_status": ("verified" if manifest else "legacy_missing_manifest"),
        "records": len(records),
        "flagged_records": sum(bool(r.quality_flags) for r in records),
        "pending_review": sum(r.review_status == "pending" for r in records),
        "rights_allow_release": sum(r.rights.public_release_allowed for r in records),
        "records_path": str(records_path),
    }
    write_json(Path("artifacts/pipelines") / f"{config.name}.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a configured corpus pilot.")
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()

    with args.config.open(encoding="utf-8") as file:
        config = PipelineConfig.model_validate(yaml.safe_load(file))

    print(json.dumps(run_pipeline(config), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
