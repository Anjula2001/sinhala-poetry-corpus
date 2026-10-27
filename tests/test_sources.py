from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from sinhala_corpus.sources import SourceRegistry, load_sources

CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs" / "sources.yaml"


@pytest.fixture
def config():
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def test_project_config_loads():
    registry = load_sources(CONFIG_PATH)
    assert registry.schema_version == 1
    assert registry.sources


def test_duplicate_source_ids_are_rejected(config):
    config["sources"].append(deepcopy(config["sources"][0]))

    with pytest.raises(ValidationError, match="Source IDs must be unique"):
        SourceRegistry.model_validate(config)


def test_unverified_source_cannot_be_enabled(config):
    config["sources"][0]["enabled"] = True
    config["sources"][0]["connectivity_status"] = "unverified"

    with pytest.raises(ValidationError, match="verified connectivity"):
        SourceRegistry.model_validate(config)


def test_public_release_requires_approved_rights(config):
    config["sources"][0]["rights"]["public_release_allowed"] = True
    config["sources"][0]["rights"]["status"] = "pending_review"

    with pytest.raises(ValidationError, match="approved rights"):
        SourceRegistry.model_validate(config)


def test_unknown_settings_are_rejected(config):
    config["collection_defaults"]["timeout_second"] = 30

    with pytest.raises(ValidationError, match="Extra inputs"):
        SourceRegistry.model_validate(config)


def test_invalid_homepage_is_rejected(config):
    config["sources"][0]["homepage"] = "not-a-url"

    with pytest.raises(ValidationError):
        SourceRegistry.model_validate(config)
