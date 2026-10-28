import os

from huggingface_hub import HfApi

STAGING_REPO = "amarakoon2001/sinhala-poetry-corpus-staging"


def check_staging_access(api: HfApi) -> str:
    info = api.repo_info(
        repo_id=STAGING_REPO,
        repo_type="dataset",
        revision="main",
    )

    if info.id != STAGING_REPO:
        raise ValueError("Unexpected staging repository.")

    if info.private is not True:
        raise ValueError("Staging repository must be private.")

    if not info.sha:
        raise ValueError("Staging repository has no identifiable commit.")

    return info.sha


def main() -> None:
    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        raise ValueError("HF_TOKEN is missing.")

    api = HfApi(
        endpoint="https://huggingface.co",
        token=token,
    )
    commit = check_staging_access(api)

    print("Staging repository:", STAGING_REPO)
    print("Private repository: verified")
    print("Read access: verified")
    print("Current commit:", commit)


if __name__ == "__main__":
    main()
