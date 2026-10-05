"""Release credentials, ordering, and retry boundaries in the workflow graph."""

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
ATTEST = "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6"


def workflow(name: str):
    # BaseLoader keeps the Actions `on` key and all permission values as strings.
    return yaml.load(
        (ROOT / ".github" / "workflows" / name).read_text(), Loader=yaml.BaseLoader
    )


def test_release_has_one_distribution_publisher_and_no_softprops():
    config = workflow("ci.yml")
    job = config["jobs"]["publish-release"]
    assert (
        "softprops/action-gh-release"
        not in (ROOT / ".github/workflows/ci.yml").read_text()
    )
    assert not {"github-release", "pypi", "docker-latest"}.intersection(config["jobs"])
    assert job["environment"] == "production"
    assert job["needs"] == ["plan", "ci-passed"]
    assert "needs.plan.outputs.release == 'true'" in job["if"]
    assert "github.repository == 'LedFx/LedFx'" in job["if"]
    assert job["concurrency"] == {
        "group": "release-publication",
        "cancel-in-progress": "false",
        "queue": "max",
    }
    assert job["permissions"]["id-token"] == "write"
    assert job["permissions"]["packages"] == "write"


def test_publication_generates_provenance_and_publishes_github_last():
    steps = workflow("ci.yml")["jobs"]["publish-release"]["steps"]
    token = next(step for step in steps if step.get("id") == "release-token")
    assert token["with"]["permission-contents"] == "write"
    assert token["with"]["permission-attestations"] == "write"
    assert not {"permission-issues", "permission-pull-requests"}.intersection(
        token["with"]
    )
    attestations = [step for step in steps if step.get("uses") == ATTEST]
    assert len(attestations) == 3
    file_attestation = next(
        step for step in attestations if "subject-path" in step["with"]
    )
    assert "release-assets/*" in file_attestation["with"]["subject-path"]
    assert "dist/*" in file_attestation["with"]["subject-path"]
    for step in attestations:
        assert "already_published != 'true'" in step["if"]
        assert (
            step["with"]["github-token"] == "${{ steps.release-token.outputs.token }}"
        )
        if "subject-digest" in step["with"]:
            assert step["with"]["push-to-registry"] == "true"
            assert step["with"]["create-storage-record"] == "false"
    pypi = next(
        step
        for step in steps
        if step.get("uses", "").startswith("pypa/gh-action-pypi-publish@")
    )
    assert pypi["with"]["skip-existing"] == "true"
    prepare = next(step for step in steps if step.get("id") == "prepare")
    promote = next(step for step in steps if step.get("id") == "promote")
    finalize = next(
        step for step in steps if "publish_release.py finalize" in step.get("run", "")
    )
    assert steps.index(prepare) < steps.index(file_attestation) < steps.index(pypi)
    assert steps.index(pypi) < steps.index(promote) < steps.index(finalize)
    assert all(steps.index(step) < steps.index(finalize) for step in attestations)
    assert "DISCORD_" not in str(steps)
    assert "OPENROUTER" not in str(steps)


def test_notifications_run_separately_on_publication_or_default_branch_retry():
    config = workflow("release-notifications.yml")
    assert config["on"]["release"]["types"] == ["published"]
    assert config["on"]["workflow_dispatch"]["inputs"]["tag"]["required"] == "true"
    assert (
        "github.event.release.tag_name || inputs.tag" in config["concurrency"]["group"]
    )
    assert config["concurrency"]["cancel-in-progress"] == "false"
    assert config["concurrency"]["queue"] == "max"
    job = config["jobs"]["notify"]
    assert "production" != job.get("environment")
    assert "github.repository == 'LedFx/LedFx'" in job["if"]
    assert "github.event.repository.default_branch" in job["if"]
    checkout = next(
        step
        for step in job["steps"]
        if step.get("uses", "").startswith("actions/checkout@")
    )
    assert checkout["with"]["ref"] == "${{ github.event.repository.default_branch }}"
    assert checkout["with"]["persist-credentials"] == "false"
    token = next(step for step in job["steps"] if step.get("id") == "state-token")
    assert token["with"]["permission-contents"] == "write"
    assert "permission-attestations" not in token["with"]
    send = next(
        step for step in job["steps"] if "announce_release.py" in step.get("run", "")
    )
    assert "GH_TOKEN" not in send.get("env", {})
    assert "RELEASE_STATE_TOKEN" in send["env"]
    assert all(
        secret in send["env"]
        for secret in (
            "DISCORD_ANNOUNCEMENTS_WEBHOOK",
            "DISCORD_RELEASETHREAD_WEBHOOK",
            "SHAUNS_OPENROUTER_KEY",
        )
    )
