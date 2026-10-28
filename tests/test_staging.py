from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from sinhala_corpus.staging import STAGING_REPO, check_staging_access


def make_api(*, private=True, repo_id=STAGING_REPO):
    return SimpleNamespace(
        repo_info=Mock(
            return_value=SimpleNamespace(
                id=repo_id,
                private=private,
                sha="a" * 40,
            )
        )
    )


def test_expected_private_repository_is_accepted():
    api = make_api()

    assert check_staging_access(api) == "a" * 40
    api.repo_info.assert_called_once_with(
        repo_id=STAGING_REPO,
        repo_type="dataset",
        revision="main",
    )


def test_public_repository_is_rejected():
    with pytest.raises(ValueError, match="must be private"):
        check_staging_access(make_api(private=False))


def test_unexpected_repository_is_rejected():
    with pytest.raises(ValueError, match="Unexpected staging"):
        check_staging_access(make_api(repo_id="someone/another-repo"))
