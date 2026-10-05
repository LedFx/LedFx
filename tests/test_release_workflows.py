"""Release credentials, ordering, and retry boundaries in the workflow graph."""

import os
import re
import shutil
import subprocess
import sys
import textwrap
import tomllib
from pathlib import Path
from typing import cast

import yaml

ROOT = Path(__file__).parents[1]
ATTEST = "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6"


SHARED = "LedFx/release-ci/actions/release@"


def mapping(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    assert all(isinstance(key, str) for key in value)
    return cast(dict[str, object], value)


def path(value: object, *keys: str) -> object:
    for key in keys:
        value = mapping(value)[key]
    return value


def text(value: object) -> str:
    assert isinstance(value, str)
    return value


def steps_for(job: object) -> list[dict[str, object]]:
    value = path(job, "steps")
    assert isinstance(value, list)
    return [mapping(step) for step in value]


def workflow(name: str) -> dict[str, object]:
    # BaseLoader keeps the Actions `on` key and all permission values as strings.
    return mapping(
        yaml.load(
            (ROOT / ".github" / "workflows" / name).read_text(), Loader=yaml.BaseLoader
        )
    )


def test_release_has_one_distribution_publisher_and_no_softprops() -> None:
    config = workflow("ci.yml")
    job = mapping(path(config, "jobs", "publish-release"))
    assert (
        "softprops/action-gh-release"
        not in (ROOT / ".github/workflows/ci.yml").read_text()
    )
    assert not {"github-release", "pypi", "docker-latest"}.intersection(
        mapping(config["jobs"])
    )
    assert job["environment"] == "production"
    assert job["needs"] == ["plan", "ci-passed"]
    assert "needs.plan.outputs.release == 'true'" in text(job["if"])
    assert "github.repository == 'LedFx/LedFx'" in text(job["if"])
    assert job["concurrency"] == {
        "group": "release-publication",
        "cancel-in-progress": "false",
        "queue": "max",
    }
    assert path(job, "permissions", "id-token") == "write"
    assert path(job, "permissions", "packages") == "write"


def test_publication_generates_provenance_and_publishes_github_last() -> None:
    steps = steps_for(path(workflow("ci.yml"), "jobs", "publish-release"))
    token = next(step for step in steps if step.get("id") == "release-token")
    assert path(token, "with", "permission-contents") == "write"
    assert path(token, "with", "permission-attestations") == "write"
    assert not {"permission-issues", "permission-pull-requests"}.intersection(
        mapping(token["with"])
    )
    attestations = [step for step in steps if step.get("uses") == ATTEST]
    assert len(attestations) == 3
    file_attestation = next(
        step for step in attestations if "subject-path" in mapping(step["with"])
    )
    assert "release-assets/*" in text(path(file_attestation, "with", "subject-path"))
    assert "dist/*" in text(path(file_attestation, "with", "subject-path"))
    for step in attestations:
        assert "already_published != 'true'" in text(step["if"])
        assert (
            path(step, "with", "github-token")
            == "${{ steps.release-token.outputs.token }}"
        )
        if "subject-digest" in mapping(step["with"]):
            assert path(step, "with", "push-to-registry") == "true"
            assert path(step, "with", "create-storage-record") == "false"
    pypi = next(
        step
        for step in steps
        if text(step.get("uses", "")).startswith("pypa/gh-action-pypi-publish@")
    )
    assert path(pypi, "with", "skip-existing") == "true"
    prepare = next(step for step in steps if step.get("id") == "prepare")
    promote = next(step for step in steps if step.get("id") == "promote")
    finalize = next(
        step
        for step in steps
        if text(step.get("uses", "")).startswith(SHARED)
        and path(step, "with", "phase") == "finalize"
    )
    assert steps.index(prepare) < steps.index(file_attestation) < steps.index(pypi)
    assert steps.index(pypi) < steps.index(promote) < steps.index(finalize)
    assert all(steps.index(step) < steps.index(finalize) for step in attestations)
    assert "DISCORD_" not in str(steps)
    assert "OPENROUTER" not in str(steps)


def test_notifications_run_separately_on_publication_or_default_branch_retry() -> None:
    config = workflow("release-notifications.yml")
    assert path(config, "on", "release", "types") == ["published"]
    assert (
        path(config, "on", "workflow_dispatch", "inputs", "tag", "required") == "true"
    )
    assert "github.event.release.tag_name || inputs.tag" in text(
        path(config, "concurrency", "group")
    )
    assert path(config, "concurrency", "cancel-in-progress") == "false"
    assert path(config, "concurrency", "queue") == "max"
    job = mapping(path(config, "jobs", "notify"))
    assert "production" != job.get("environment")
    assert "github.repository == 'LedFx/LedFx'" in text(job["if"])
    assert "github.event.repository.default_branch" in text(job["if"])
    checkout = next(
        step
        for step in steps_for(job)
        if text(step.get("uses", "")).startswith("actions/checkout@")
    )
    assert (
        path(checkout, "with", "ref") == "${{ github.event.repository.default_branch }}"
    )
    assert path(checkout, "with", "persist-credentials") == "false"
    token = next(step for step in steps_for(job) if step.get("id") == "state-token")
    assert path(token, "with", "permission-contents") == "write"
    assert "permission-attestations" not in mapping(token["with"])
    send = next(
        step
        for step in steps_for(job)
        if "announce_release.py" in text(step.get("run", ""))
    )
    assert "GH_TOKEN" not in mapping(send.get("env", {}))
    assert "RELEASE_STATE_TOKEN" in mapping(send["env"])
    assert all(
        secret in mapping(send["env"])
        for secret in (
            "DISCORD_ANNOUNCEMENTS_WEBHOOK",
            "DISCORD_RELEASETHREAD_WEBHOOK",
            "SHAUNS_OPENROUTER_KEY",
        )
    )


def test_shared_policy_and_same_run_inputs_are_explicit() -> None:
    job = path(workflow("ci.yml"), "jobs", "publish-release")
    condition = text(path(job, "if"))
    assert "!cancelled()" in condition
    assert "needs.plan.result == 'success'" in condition
    assert "needs.ci-passed.result == 'success'" in condition
    assert "github.event_name == 'push'" in condition
    assert "startsWith(github.ref, 'refs/tags/v')" in condition
    steps = steps_for(job)
    shared = [step for step in steps if text(step.get("uses", "")).startswith(SHARED)]
    raw = (ROOT / ".github/workflows/ci.yml").read_text()
    pins = re.findall(
        r"uses: LedFx/release-ci/actions/release@([0-9a-f]{40})(?:[ \t]+#.*)?[ \t]*$",
        raw,
        re.MULTILINE,
    )
    assert len(pins) == 4 and len(set(pins)) == 1
    assert raw.count("uses: " + SHARED) == 4
    assert [path(step, "with", "phase") for step in shared] == [
        "prepare",
        "check-upload",
        "promote",
        "finalize",
    ]
    for step in shared:
        assert mapping(step["with"]) == {
            "phase": path(step, "with", "phase"),
            "project": "release-tools",
            "assets": "release-assets",
            "dist": "dist",
            "docker-digests": "docker-digests",
            "snapshot": "${{ runner.temp }}/release-snapshot.json",
        }
        assert (
            path(step, "env", "GH_TOKEN") == "${{ steps.release-token.outputs.token }}"
        )
    pypi = next(
        step for step in steps if text(step.get("uses", "")).startswith("pypa/")
    )
    assert steps.index(shared[1]) < steps.index(pypi)
    assert pypi["if"] == "steps.upload.outputs.pypi_upload == 'true'"
    downloads = [
        mapping(step["with"])
        for step in steps
        if text(step.get("uses", "")).startswith("actions/download-artifact@")
    ]
    assert downloads == [
        {"pattern": "release-*", "merge-multiple": "true", "path": "release-assets/"},
        {"name": "python-dist", "path": "dist/"},
        {"pattern": "docker-*", "merge-multiple": "true", "path": "docker-digests/"},
    ]
    config = mapping(tomllib.loads((ROOT / "pyproject.toml").read_text()))
    assert path(config, "project", "name") == "LedFx"
    settings = mapping(path(config, "tool", "release-ci"))
    assert set(settings) == {"github-distributions", "assets", "oci"}
    assert settings["github-distributions"] is False
    assert settings["assets"] == [
        "LedFx-{tag_version}-win-x64.zip",
        "LedFx-{tag_version}-win-x64-setup.zip",
        "LedFx-{tag_version}-osx-arm64.tar.gz",
        "LedFx-{tag_version}-osx-intel.tar.gz",
    ]
    images = settings["oci"]
    assert isinstance(images, list)
    assert images == [
        {
            "image": image,
            "platforms": ["linux/amd64", "linux/arm64"],
            "promote-latest": True,
        }
        for image in ("ghcr.io/ledfx/ledfx", "docker.io/ledfxorg/ledfx")
    ]
    assert not (ROOT / ".github/release-policy.json").exists()
    assert "sparse-checkout-cone-mode: false" in raw
    assert "actions/plan@" not in raw
    assert "policy:" not in raw
    for step in steps:
        if step.get("uses") == ATTEST and "subject-digest" in mapping(step["with"]):
            subject = text(path(step, "with", "subject-digest"))
            assert "fromJSON(steps.promote.outputs.image_digests)" in subject
            assert any(text(mapping(image)["image"]) in subject for image in images)
    retained = next(
        step
        for step in steps
        if text(step.get("uses", "")).startswith("actions/upload-artifact@")
    )
    assert retained["if"] == "always() && steps.prepare.outcome == 'success'"
    assert "${{ runner.temp }}/release-snapshot.json" in text(
        path(retained, "with", "path")
    )
    assert text(path(retained, "with", "path")).count("outputs.bundle-path") == 3


def test_upload_sidecars_leave_frozen_inputs_unchanged(tmp_path: Path) -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    match = re.search(
        r"(?m)^      - name: Stage verified distributions for PyPI\n"
        r"(?:(?:^        .*\n)|(?:^\n))*?^        run: \|\n"
        r"((?:^          .*\n|^\n)+)",
        workflow,
    )
    assert match is not None, "The uploader needs a separate verified input copy"
    stage = workflow.split("      - name: Stage verified distributions for PyPI\n", 1)[
        1
    ].split("\n      - ", 1)[0]
    assert "if: steps.upload.outputs.pypi_upload == 'true'" in stage
    assert "working-directory: ${{ github.workspace }}" in stage
    assert workflow.index("phase: check-upload") < workflow.index(
        "Stage verified distributions for PyPI"
    )
    uploader = workflow.split("uses: pypa/gh-action-pypi-publish@", 1)[1].split(
        "\n      - ", 1
    )[0]
    assert "packages-dir: pypi-dist/" in uploader
    script = textwrap.dedent(match.group(1))
    bash = "bash"
    if sys.platform == "win32":
        # The Windows PATH may resolve bash to the WSL launcher instead.
        git = shutil.which("git")
        assert git is not None, "Git for Windows is required for workflow tests"
        git_bash = next(
            (
                parent / "bin" / "bash.exe"
                for parent in Path(git).resolve().parents
                if (parent / "bin" / "bash.exe").is_file()
            ),
            None,
        )
        assert git_bash is not None, "Git for Windows Bash was not found"
        bash = str(git_bash)
    original = tmp_path / "dist"
    original.mkdir()
    frozen = {
        "example-1.0-py3-none-any.whl": b"tested wheel",
        "example-1.0.tar.gz": b"tested sdist",
    }
    for name, data in frozen.items():
        (original / name).write_bytes(data)
    result = subprocess.run(
        [bash, "-euo", "pipefail", "-c", script],
        cwd=tmp_path,
        env={**os.environ, "GITHUB_WORKSPACE": str(tmp_path)},
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    staging = tmp_path / "pypi-dist"
    assert {p.name: p.read_bytes() for p in staging.iterdir()} == frozen
    for name in frozen:
        (staging / (name + ".publish.attestation")).write_bytes(
            b"generated PyPI sidecar"
        )
    assert {p.name: p.read_bytes() for p in original.iterdir()} == frozen
    before_retry = {p.name: p.read_bytes() for p in staging.iterdir()}
    retry = subprocess.run(
        [bash, "-euo", "pipefail", "-c", script],
        cwd=tmp_path,
        env={**os.environ, "GITHUB_WORKSPACE": str(tmp_path)},
        capture_output=True,
        check=False,
    )
    assert retry.returncode != 0
    assert {p.name: p.read_bytes() for p in staging.iterdir()} == before_retry
    assert {p.name: p.read_bytes() for p in original.iterdir()} == frozen
