import argparse
import hashlib
import html
import json
import re
from pathlib import Path

VERSE_MARKER = re.compile(
    r"^[ \t]*([0-9]+)\.[ \t]*(?=<br\s*/?>)",
    re.MULTILINE | re.IGNORECASE,
)
LINE_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)
CATEGORY_LINE = re.compile(
    r"^[ \t]*\[\[Category:[^\]\n]+\]\][ \t]*$",
    re.MULTILINE,
)
EXPECTED_TITLE = "සිරිත් මල්දම/සිරිත් මල්දම (1 කොටස)"


def parse_verses(text: str) -> list[dict]:
    markers = list(VERSE_MARKER.finditer(text))
    if not markers:
        raise ValueError("No supported verse markers found.")

    numbers = [int(marker.group(1)) for marker in markers]
    if numbers != list(range(1, len(numbers) + 1)):
        raise ValueError("Verse numbering must start at 1 and be consecutive.")

    verses = []

    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        body = text[marker.end() : end]
        body = CATEGORY_LINE.sub("", body)
        body = LINE_BREAK.sub("\n", body)
        body = html.unescape(body)

        lines = []
        for line in body.splitlines():
            # Normalize horizontal layout spacing, preserving Sinhala characters.
            cleaned = re.sub(r"[ \t\u00a0]+", " ", line).strip()
            if cleaned:
                lines.append(cleaned)

        cleaned_text = "\n".join(lines)
        flags = []

        if len(lines) != 4:
            flags.append("unexpected_line_count")
        if re.search(r"[<>{}\[\]]", cleaned_text):
            flags.append("possible_markup_or_transcription_artifact")

        verses.append(
            {
                "verse_number": numbers[index],
                "text": cleaned_text,
                "line_count": len(lines),
                "raw_start_line": text.count("\n", 0, marker.start()) + 1,
                "quality_flags": flags,
                "review_status": "pending",
            }
        )

    return verses


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract review candidates from Sirith Maldama part 1."
    )
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    raw = args.snapshot.read_bytes()
    payload = json.loads(raw)
    page = payload["query"]["pages"][0]
    revision = page["revisions"][0]

    # This parser has only been inspected against this specific snapshot.
    if page["title"] != EXPECTED_TITLE or revision["revid"] != 1042800:
        raise ValueError("Unsupported page or revision for this parser.")

    text = revision["slots"]["main"]["content"]
    verses = parse_verses(text)
    flagged = [verse["verse_number"] for verse in verses if verse["quality_flags"]]

    result = {
        "parser_version": 1,
        "source_id": "wikisource_si",
        "page_id": page["pageid"],
        "title": page["title"],
        "revision_id": revision["revid"],
        "snapshot_sha256": hashlib.sha256(raw).hexdigest(),
        "public_release_allowed": False,
        "verse_count": len(verses),
        "flagged_verse_numbers": flagged,
        "verses": verses,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("Verse candidates:", len(verses))
    print("Flagged verses:", flagged)
    print("Review status: pending for all candidates")
    print("Saved:", args.output)


if __name__ == "__main__":
    main()
