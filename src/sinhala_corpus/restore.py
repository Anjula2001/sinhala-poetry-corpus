import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from huggingface_hub import HfApi, hf_hub_download

from sinhala_corpus.staging import STAGING_REPO, check_staging_access
from sinhala_corpus.upload import BUNDLE_FILES


def verify_bundle(
    files: dict[str, bytes],
    *,
    run_id: str,
    run_attempt: str,
    code_commit: str,
) -> dict:
    expected = set(BUNDLE_FILES)

    if set(files) != expected | {"run.json"}:
        raise ValueError("Restored bundle has missing or unexpected files.")

    metadata = json.loads(files["run.json"])

    if (
        metadata["bundle_version"] != 1
        or metadata["github_repository"] != "Anjula2001/sinhala-poetry-corpus"
        or metadata["github_run_id"] != run_id
        or metadata["github_run_attempt"] != run_attempt
        or metadata["code_commit"] != code_commit
    ):
        raise ValueError("Restored run metadata does not match the expected run.")

    if set(metadata["files"]) != expected:
        raise ValueError("Manifest contains missing or unexpected file paths.")

    total_bytes = 0

    for name in BUNDLE_FILES:
        content = files[name]
        entry = metadata["files"][name]

        if type(entry["size_bytes"]) is not int:
            raise ValueError(f"Invalid file size: {name}")

        if len(content) != entry["size_bytes"]:
            raise ValueError(f"File size mismatch: {name}")

        if hashlib.sha256(content).hexdigest() != entry["sha256"]:
            raise ValueError(f"Checksum mismatch: {name}")

        total_bytes += len(content)

    return {
        "status": "verified",
        "files_verified": len(BUNDLE_FILES),
        "payload_bytes_verified": total_bytes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a private staging backup.")
    parser.add_argument("--commit", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--code-commit", required=True)
    args = parser.parse_args()

    for value in (args.commit, args.code_commit):
        if not re.fullmatch(r"[0-9a-f]{40}", value):
            parser.error(
                "Commit SHAs must contain 40 lowercase hexadecimal characters."
            )

    for value in (args.run_id, args.run_attempt):
        if not re.fullmatch(r"[0-9]+", value):
            parser.error("Run ID and attempt must contain digits only.")

    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        raise ValueError("HF_TOKEN is missing.")

    api = HfApi(endpoint="https://huggingface.co", token=token)
    check_staging_access(api)

    prefix = f"runs/{args.run_id}/{args.run_attempt}"

    # A fresh temporary cache avoids reusing files from the upload workspace.
    with TemporaryDirectory(prefix="corpus-restore-") as cache:
        files = {}
        for name in (*BUNDLE_FILES, "run.json"):
            path = hf_hub_download(
                repo_id=STAGING_REPO,
                repo_type="dataset",
                filename=f"{prefix}/{name}",
                revision=args.commit,
                token=token,
                endpoint="https://huggingface.co",
                cache_dir=cache,
            )
            files[name] = Path(path).read_bytes()

        result = verify_bundle(
            files,
            run_id=args.run_id,
            run_attempt=args.run_attempt,
            code_commit=args.code_commit,
        )

    report = {
        **result,
        "huggingface_commit": args.commit,
        "github_run_id": args.run_id,
        "github_run_attempt": args.run_attempt,
        "code_commit": args.code_commit,
    }

    output = Path("artifacts/restore-checks") / f"{args.run_id}-{args.run_attempt}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    print("Restore check: verified")
    print("Payload files verified:", result["files_verified"])
    print("Hugging Face commit:", args.commit)
    print("Report:", output)


if __name__ == "__main__":
    main()
