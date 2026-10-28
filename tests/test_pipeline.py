import json

import httpx
import pytest

from sinhala_corpus.pipeline import PipelineConfig, run_pipeline


@pytest.fixture
def pipeline_setup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    config_dir = tmp_path / "configs"
    config_dir.mkdir()

    sources = config_dir / "sources.yaml"
    sources.write_text(
        """
schema_version: 1
collection_defaults:
  timeout_seconds: 10
  request_interval_seconds: 2
  max_retries: 0
  max_records_per_run: 20
sources:
  - id: wikisource_si
    name: Test source
    homepage: https://example.org
    base_url: https://example.org/api.php
    content_types: [poem]
    access_method: mediawiki_api
    enabled: true
    connectivity_status: verified
    rights:
      status: pending_review
""",
        encoding="utf-8",
    )

    reviews = config_dir / "reviews.yaml"
    reviews.write_text(
        """
schema_version: 1
source_id: wikisource_si
revision_id: 1042800
decisions: []
""",
        encoding="utf-8",
    )

    snapshot = tmp_path / "data/raw/wikisource_si/revision-1042800.json"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text(
        json.dumps(
            {
                "query": {
                    "pages": [
                        {
                            "pageid": 101231,
                            "title": "සිරිත් මල්දම/සිරිත් මල්දම (1 කොටස)",
                            "revisions": [
                                {
                                    "revid": 1042800,
                                    "timestamp": "2023-04-07T03:29:00Z",
                                    "slots": {
                                        "main": {
                                            "content": ("01.<br>අ\n<br>ආ\n<br>ඇ\n<br>ඈ")
                                        }
                                    },
                                }
                            ],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    config = PipelineConfig(
        schema_version=1,
        name="test-pilot",
        source_id="wikisource_si",
        revision_id=1042800,
        source_config=sources,
        review_file=reviews,
    )
    return config, snapshot


def test_cached_pipeline_runs_without_network(pipeline_setup, monkeypatch):
    config, snapshot = pipeline_setup
    original = snapshot.read_bytes()

    def block_network(*args, **kwargs):
        raise AssertionError("Cached pipeline must not use the network.")

    monkeypatch.setattr(httpx.Client, "get", block_network)

    summary = run_pipeline(config)
    records_path = snapshot.parents[3] / summary["records_path"]
    record = json.loads(records_path.read_text(encoding="utf-8"))

    assert summary["records"] == 1
    assert summary["manifest_status"] == "legacy_missing_manifest"
    assert record["retrieved_at"] is None
    assert record["review_status"] == "pending"
    assert record["rights"]["public_release_allowed"] is False
    assert snapshot.read_bytes() == original


def test_invalid_existing_manifest_stops_pipeline(pipeline_setup):
    config, snapshot = pipeline_setup
    snapshot.with_suffix(".meta.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError):
        run_pipeline(config)

    assert not (
        snapshot.parents[3] / "data/processed/test-pilot-records.jsonl"
    ).exists()


def test_wrong_snapshot_revision_stops_pipeline(pipeline_setup):
    config, snapshot = pipeline_setup
    payload = json.loads(snapshot.read_text(encoding="utf-8"))
    payload["query"]["pages"][0]["revisions"][0]["revid"] = 999
    snapshot.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="supported work/revision"):
        run_pipeline(config)
