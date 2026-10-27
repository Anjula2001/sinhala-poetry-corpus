from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    model_validator,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CollectionDefaults(StrictModel):
    timeout_seconds: float = Field(gt=0)
    request_interval_seconds: float = Field(gt=0)
    max_retries: int = Field(ge=0)
    max_records_per_run: int = Field(gt=0)


class SourceRights(StrictModel):
    status: Literal["pending_review", "approved", "rejected"]
    declared_database_license: str | None = None
    content_license: str | None = None
    evidence_urls: list[HttpUrl] = Field(default_factory=list)
    public_release_allowed: bool = False

    @model_validator(mode="after")
    def validate_public_release(self) -> Self:
        if self.public_release_allowed:
            if self.status != "approved" or not self.evidence_urls:
                raise ValueError(
                    "Public release requires approved rights and evidence URLs."
                )
        return self


class SourceConfig(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1)
    homepage: HttpUrl
    documentation_url: HttpUrl | None = None
    base_url: HttpUrl | None = None

    content_types: list[
        Literal[
            "poem",
            "free_verse",
            "folk_poem",
            "folk_song",
            "song_lyrics",
        ]
    ] = Field(min_length=1)

    access_method: Literal["api", "mediawiki_api", "manual"]
    enabled: bool = False
    connectivity_status: Literal["unverified", "verified", "unavailable"]
    rights: SourceRights
    notes: str = ""

    @model_validator(mode="after")
    def validate_enabled_source(self) -> Self:
        if self.enabled:
            if self.connectivity_status != "verified":
                raise ValueError("Enabled sources must have verified connectivity.")
            if self.access_method != "manual" and self.base_url is None:
                raise ValueError("Enabled API sources require a base URL.")
        return self


class SourceRegistry(StrictModel):
    schema_version: Literal[1]
    collection_defaults: CollectionDefaults
    sources: list[SourceConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> Self:
        ids = [source.id for source in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("Source IDs must be unique.")
        return self


def load_sources(path: Path) -> SourceRegistry:
    with path.open(encoding="utf-8") as file:
        content = yaml.safe_load(file)
    return SourceRegistry.model_validate(content)
