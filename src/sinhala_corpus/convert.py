import argparse
import hashlib
import json
from pathlib import Path

from sinhala_corpus.manifests import (
    SnapshotManifest,
    load_manifest,
    verify_snapshot_content,
)
from sinhala_corpus.parsers.sirith_maldama import EXPECTED_TITLE, parse_verses
from sinhala_corpus.reviews import ReviewFile, load_reviews
from sinhala_corpus.schema import CorpusRecord, ExtractionProvenance


def build_records(
    raw: bytes,
    candidates: dict,
    reviews: ReviewFile,
    manifest: SnapshotManifest | None = None,
) -> list[CorpusRecord]:
    payload = json.loads(raw)
    page = payload["query"]["pages"][0]
    revision = page["revisions"][0]
    revision_id = revision["revid"]
    checksum = hashlib.sha256(raw).hexdigest()
    if manifest is not None:
        verify_snapshot_content(raw, manifest)

        if manifest.source_id != "wikisource_si" or manifest.revision_id != revision_id:
            raise ValueError("Manifest source or revision mismatch.")

    if page["title"] != EXPECTED_TITLE or revision_id != 1042800:
        raise ValueError("Unsupported source page or revision.")

    if candidates["source_id"] != "wikisource_si":
        raise ValueError("Candidate source mismatch.")

    if (
        candidates["page_id"] != page["pageid"]
        or candidates["revision_id"] != revision_id
        or candidates["snapshot_sha256"] != checksum
        or candidates["parser_version"] != 1
    ):
        raise ValueError("Candidate provenance does not match the snapshot.")

    if (
        reviews.source_id != candidates["source_id"]
        or reviews.revision_id != revision_id
    ):
        raise ValueError("Review source or revision mismatch.")

    # Detect accidental edits to generated candidate content.
    expected = parse_verses(revision["slots"]["main"]["content"])
    if candidates["verses"] != expected:
        raise ValueError("Candidates differ from the parser output.")

    decisions = {decision.verse_number: decision for decision in reviews.decisions}
    verse_numbers = {verse["verse_number"] for verse in expected}
    if set(decisions) - verse_numbers:
        raise ValueError("Review refers to an unknown verse.")

    records = []

    for verse in expected:
        number = verse["verse_number"]
        decision = decisions.get(number)

        provenance = ExtractionProvenance(
            source_revision_id=revision_id,
            source_revision_timestamp=revision["timestamp"],
            source_page_title=page["title"],
            snapshot_sha256=checksum,
            parser_version=1,
            segment_number=number,
            raw_start_line=verse["raw_start_line"],
            reviewer=decision.reviewer if decision else None,
            reviewed_at=decision.reviewed_at if decision else None,
            review_notes=decision.notes if decision else "",
        )

        record = CorpusRecord(
            id=f"wikisource_si:{page['pageid']}:{revision_id}:verse:{number}",
            # Parent work page; shared by all verses and parts of this work.
            work_id="wikisource_si:82432",
            title=None,
            text=verse["text"],
            type="poem",
            authors=["ඇම්.ඇල්.සිල්වා ගුරු මුහන්දිරම්"],
            origin="human",
            source_id="wikisource_si",
            source_record_id=str(page["pageid"]),
            source_url=(f"https://wikisource.org/w/index.php?oldid={revision_id}"),
            retrieved_at=manifest.retrieved_at if manifest else None,
            source_updated_at=revision["timestamp"],
            review_status=decision.status if decision else "pending",
            quality_flags=verse["quality_flags"],
            provenance=provenance,
        )
        records.append(record)

    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Build working corpus records.")
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--reviews", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    raw = args.snapshot.read_bytes()
    manifest_path = args.snapshot.with_suffix(".meta.json")

    # Missing manifests are allowed for legacy snapshots.
    # Existing but invalid manifests must fail validation.
    manifest = load_manifest(args.snapshot) if manifest_path.exists() else None

    records = build_records(
        raw,
        json.loads(args.candidates.read_text(encoding="utf-8")),
        load_reviews(args.reviews),
        manifest=manifest,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(record.model_dump_json() + "\n" for record in records),
        encoding="utf-8",
    )

    print("Records:", len(records))
    print("Pending review:", sum(r.review_status == "pending" for r in records))
    print(
        "Rights allow release:", sum(r.rights.public_release_allowed for r in records)
    )
    print("Saved:", args.output)


if __name__ == "__main__":
    main()
