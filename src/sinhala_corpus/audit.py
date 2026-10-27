import argparse
import hashlib
import json
import re
from pathlib import Path

NUMBER_LINE = re.compile(r"\s*[0-9]+(?:\s+[0-9]+)*\s*")


def audit_layout(text: str) -> dict:
    single = []
    multiple = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        if not NUMBER_LINE.fullmatch(line):
            continue

        numbers = [int(value) for value in line.split()]
        entry = {"line": line_number, "numbers": numbers}

        if len(numbers) == 1:
            single.append(entry)
        else:
            multiple.append(entry)

    return {
        "line_count": len(text.splitlines()),
        "single_number_line_count": len(single),
        "multiple_number_line_count": len(multiple),
        "multiple_number_lines": multiple,
        "layout_status": "requires_review" if multiple else "not_flagged",
        "quality_flags": (["possible_merged_columns"] if multiple else []),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit raw Wikisource layout.")
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    raw = args.snapshot.read_bytes()
    payload = json.loads(raw)
    page = payload["query"]["pages"][0]
    revision = page["revisions"][0]
    text = revision["slots"]["main"]["content"]

    report = {
        "audit_version": 1,
        "source_id": "wikisource_si",
        "page_id": page["pageid"],
        "title": page["title"],
        "revision_id": revision["revid"],
        "snapshot_sha256": hashlib.sha256(raw).hexdigest(),
        **audit_layout(text),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("Layout status:", report["layout_status"])
    print("Multiple-number lines:", report["multiple_number_line_count"])
    print("Report saved:", args.output)


if __name__ == "__main__":
    main()
