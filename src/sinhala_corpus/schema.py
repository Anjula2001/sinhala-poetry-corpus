from typing import Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)

ContentType = Literal[
    "poem",
    "free_verse",
    "folk_poem",
    "folk_song",
    "song_lyrics",
]


class RecordRights(BaseModel):
    model_config = ConfigDict(extra="forbid")

    basis: Literal[
        "unknown",
        "public_domain",
        "open_license",
        "permission",
    ] = "unknown"

    license: str | None = None
    evidence_urls: list[HttpUrl] = Field(default_factory=list)
    public_release_allowed: bool = False

    @model_validator(mode="after")
    def validate_release_evidence(self) -> Self:
        if self.public_release_allowed:
            if self.basis == "unknown" or not self.evidence_urls:
                raise ValueError(
                    "Public release requires a known rights basis and evidence."
                )
            if self.basis == "open_license" and not self.license:
                raise ValueError("Open-license releases require a license identifier.")
        return self


class ExtractionProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_revision_id: int = Field(gt=0, strict=True)
    source_revision_timestamp: AwareDatetime
    source_page_title: str = Field(min_length=1)
    snapshot_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    parser_version: int = Field(gt=0, strict=True)

    segment_type: Literal["verse"] = "verse"
    segment_number: int = Field(gt=0, strict=True)
    raw_start_line: int = Field(gt=0, strict=True)

    reviewer: str | None = None
    reviewed_at: AwareDatetime | None = None
    review_notes: str = ""


class CorpusRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    id: str = Field(min_length=1)
    work_id: str | None = Field(default=None, min_length=1)

    title: str | None = Field(default=None, min_length=1)
    text: str = Field(min_length=1)
    type: ContentType
    language: Literal["si"] = "si"

    authors: list[str] = Field(default_factory=list)
    singers: list[str] = Field(default_factory=list)
    composers: list[str] = Field(default_factory=list)
    origin: Literal["human", "machine", "unknown"] = "unknown"

    source_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    source_record_id: str = Field(min_length=1)
    source_url: HttpUrl
    retrieved_at: AwareDatetime | None = None
    source_updated_at: AwareDatetime | None = None
    provenance: ExtractionProvenance | None = None

    rights: RecordRights = Field(default_factory=RecordRights)
    review_status: Literal["pending", "approved", "rejected"] = "pending"
    quality_flags: list[str] = Field(default_factory=list)

    @field_validator("id", "work_id", "title", "text", "source_record_id")
    @classmethod
    def reject_blank_values(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Value must not contain only whitespace.")
        return value

    @field_validator("authors", "singers", "composers", "quality_flags")
    @classmethod
    def reject_blank_list_items(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("List items must not be blank.")
        return values
