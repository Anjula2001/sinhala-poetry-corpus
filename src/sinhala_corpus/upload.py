import hashlib
import json
import os
import re
from pathlib import Path

from huggingface_hub import CommitOperationAdd, HfApi

from sinhala_corpus.manifests import load_manifest
from sinhala_corpus.staging import STAGING_REPO, check_staging_access

BUNDLE_FILES = (
    "data/raw/wikisource_si/revision-1042800.json",
    "data/raw/wikisource_si/revision-1042800.meta.json",
    "data/processed/sirith-maldama-part1-candidates.json",
    "data/processed/sirith-maldama-part1-records.jsonl",
    "artifacts/audits/sirith-maldama-part1.json",
    "artifacts/pipelines/sirith-maldama-part1.json",
)


def prepare_bundle(root: Path) -> dict[str, bytes]:
    root = root.resolve()
    files = {}

    for relative in BUNDLE_FILES:
        path = root / relative
        if (
            path.is_symlink()
            or not path.resolve().is_relative_to(root)
            or not path.is_file()
        ):
            raise ValueError(f"Required bundle file is missing or unsafe: {relative}")

        files[relative] = path.read_bytes()

    manifest = load_manifest(root / BUNDLE_FILES[0])
    summary = json.loads(files[BUNDLE_FILES[-1]])

    if (
        manifest.source_id != "wikisource_si"
        or manifest.revision_id != 1042800
        or hashlib.sha256(files[BUNDLE_FILES[0]]).hexdigest() != manifest.sha256
        or summary["source_id"] != manifest.source_id
        or summary["revision_id"] != manifest.revision_id
        or summary["snapshot_sha256"] != manifest.sha256
        or summary["manifest_status"] != "verified"
    ):
        raise ValueError("Bundle provenance verification failed.")

    return files


def upload_bundle(
    api: HfApi,
    *,
    root: Path,
    run_id: str,
    run_attempt: str,
    code_commit: str,
) -> str:
    if not re.fullmatch(r"[0-9]+", run_id):
        raise ValueError("Invalid GitHub run ID.")
    if not re.fullmatch(r"[0-9]+", run_attempt):
        raise ValueError("Invalid GitHub run attempt.")
    if not re.fullmatch(r"[0-9a-f]{40}", code_commit):
        raise ValueError("Invalid source code commit SHA.")

    parent_commit = check_staging_access(api)
    files = prepare_bundle(root)
    prefix = f"runs/{run_id}/{run_attempt}"

    existing = api.list_repo_files(
        repo_id=STAGING_REPO,
        repo_type="dataset",
        revision=parent_commit,
    )
    if any(path.startswith(f"{prefix}/") for path in existing):
        raise ValueError("This run bundle already exists; refusing to overwrite it.")

    run_metadata = {
        "bundle_version": 1,
        "github_repository": "Anjula2001/sinhala-poetry-corpus",
        "github_run_id": run_id,
        "github_run_attempt": run_attempt,
        "code_commit": code_commit,
        "files": {
            name: {
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            for name, content in files.items()
        },
    }
    files["run.json"] = (
        json.dumps(run_metadata, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")

    result = api.create_commit(
        repo_id=STAGING_REPO,
        repo_type="dataset",
        revision="main",
        parent_commit=parent_commit,
        commit_message=f"Store pilot bundle for GitHub run {run_id}/{run_attempt}",
        operations=[
            CommitOperationAdd(
                path_in_repo=f"{prefix}/{name}",
                path_or_fileobj=content,
            )
            for name, content in files.items()
        ],
    )
    return result.oid


def main() -> None:
    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        raise ValueError("HF_TOKEN is missing.")

    api = HfApi(endpoint="https://huggingface.co", token=token)
    commit = upload_bundle(
        api,
        root=Path.cwd(),
        run_id=os.environ["GITHUB_RUN_ID"],
        run_attempt=os.environ["GITHUB_RUN_ATTEMPT"],
        code_commit=os.environ["GITHUB_SHA"],
    )

    print("Private staging upload completed.")
    print("Repository:", STAGING_REPO)
    print("Hugging Face commit:", commit)


if __name__ == "__main__":
    main()
