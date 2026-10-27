import hashlib
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl


class SnapshotManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest_version: Literal[1] = 1
    source_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    revision_id: int = Field(gt=0, strict=True)
    api_url: HttpUrl
    retrieved_at: AwareDatetime
    size_bytes: int = Field(gt=0, strict=True)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def verify_snapshot(path: Path, manifest: SnapshotManifest) -> None:
    raw = path.read_bytes()

    if len(raw) != manifest.size_bytes:
        raise ValueError("Snapshot size does not match the manifest.")

    if hashlib.sha256(raw).hexdigest() != manifest.sha256:
        raise ValueError("Snapshot checksum does not match the manifest.")


def write_manifest(
    snapshot_path: Path,
    manifest: SnapshotManifest,
) -> Path:
    verify_snapshot(snapshot_path, manifest)
    manifest_path = snapshot_path.with_suffix(".meta.json")

    with manifest_path.open("x", encoding="utf-8") as file:
        file.write(manifest.model_dump_json(indent=2) + "\n")

    return manifest_path


def load_manifest(snapshot_path: Path) -> SnapshotManifest:
    manifest_path = snapshot_path.with_suffix(".meta.json")
    manifest = SnapshotManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    verify_snapshot(snapshot_path, manifest)
    return manifest
