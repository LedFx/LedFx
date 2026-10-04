"""Verified release publication contracts, with no live registry requests."""

import hashlib
import importlib.util
import io
import json
import subprocess
import tarfile
import zipfile
from email.message import Message
from pathlib import Path
from typing import TypedDict
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import pytest

PATH = Path(__file__).parents[1] / ".github/ci_scripts/publish_release.py"
SPEC = importlib.util.spec_from_file_location("publish_release", PATH)
assert SPEC and SPEC.loader
publication = importlib.util.module_from_spec(SPEC)
if PATH.exists():
    SPEC.loader.exec_module(publication)


class PypiFile(TypedDict):
    filename: str
    digests: dict[str, str]


class PypiResponse(TypedDict):
    urls: list[PypiFile]


Inputs = tuple[Path, Path, Path, Path]

TAG = "v2.2.0"
SHA = "a" * 40
REGISTRIES = ["ghcr.io/ledfx/ledfx", "ledfxorg/ledfx"]
DIGESTS = {"amd64": "sha256:" + "b" * 64, "arm64": "sha256:" + "c" * 64}
ENV = {
    "GITHUB_REPOSITORY": "LedFx/LedFx",
    "GITHUB_REF_NAME": TAG,
    "GITHUB_SHA": SHA,
    "GH_TOKEN": "secret-token",
    "GHCR_IMAGE": REGISTRIES[0],
    "DOCKERHUB_IMAGE": REGISTRIES[1],
}


@pytest.mark.parametrize(
    "tag,prerelease,releases,expected",
    [
        (TAG, False, [], True),
        (TAG, False, [{"tag_name": "v2.1.9", "draft": False}], True),
        ("v2.1.10", False, [{"tag_name": TAG, "draft": False}], False),
        (TAG, False, [{"tag_name": "v10.0.0", "draft": False}], False),
        (TAG, False, [{"tag_name": "v3.0.0", "draft": True}], True),
        (TAG, False, [{"tag_name": "v3.0.0", "prerelease": True}], True),
        ("v2.3.0-rc.1", True, [], False),
        (TAG, True, [], False),
    ],
    ids=["first", "new", "old", "numeric", "draft", "pre", "rc", "flag"],
)
def test_latest_eligibility(
    tag: str, prerelease: bool, releases: list[dict[str, object]], expected: bool
):
    assert publication.should_promote_latest(tag, prerelease, releases) is expected


@pytest.fixture
def inputs(tmp_path: Path):
    assets = tmp_path / "assets"
    dist = tmp_path / "dist"
    docker = tmp_path / "docker"
    for directory in (assets, dist, docker):
        directory.mkdir()
    for name in (
        "LedFx-2.2.0-win-x64.zip",
        "LedFx-2.2.0-win-x64-setup.zip",
        "LedFx-2.2.0-osx-arm64.tar.gz",
        "LedFx-2.2.0-osx-intel.tar.gz",
    ):
        (assets / name).write_bytes(name.encode())
    with zipfile.ZipFile(dist / "ledfx-2.2.0-py3-none-any.whl", "w") as wheel:
        wheel.writestr(
            "ledfx-2.2.0.dist-info/METADATA", "Name: ledfx\nVersion: 2.2.0\n"
        )
    metadata = b"Name: ledfx\nVersion: 2.2.0\n"
    with tarfile.open(dist / "ledfx-2.2.0.tar.gz", "w:gz") as archive:
        info = tarfile.TarInfo("ledfx-2.2.0/PKG-INFO")
        info.size = len(metadata)
        archive.addfile(info, io.BytesIO(metadata))
    for arch, digest in DIGESTS.items():
        (docker / f"docker-{arch}.txt").write_text(
            "\n".join(f"{registry}@{digest}" for registry in REGISTRIES)
        )
    return assets, dist, docker, tmp_path / "snapshot.json"


def publisher(inputs: Inputs):
    return publication.Publisher(*inputs, environment=ENV)


def pypi_files(dist: Path) -> PypiResponse:
    return {
        "urls": [
            {
                "filename": file.name,
                "digests": {"sha256": hashlib.sha256(file.read_bytes()).hexdigest()},
            }
            for file in dist.iterdir()
        ]
    }


class Services:
    def __init__(
        self,
        inputs: Inputs,
        draft: bool = True,
        asset_count: int = 0,
        uploaded: bool = False,
    ):
        self.inputs = inputs
        self.release = {
            "id": 42,
            "tag_name": TAG,
            "draft": draft,
            "prerelease": False,
            "body": "Release notes",
            "assets": [],
        }
        for index, file in enumerate(sorted(inputs[0].iterdir())[:asset_count]):
            self.release["assets"].append(
                {
                    "id": index + 1,
                    "name": file.name,
                    "digest": "sha256:" + hashlib.sha256(file.read_bytes()).hexdigest(),
                }
            )
        self.pypi: PypiResponse = pypi_files(inputs[1]) if uploaded else {"urls": []}
        self.tags = {}
        self.writes: list[list[str]] = []
        self.tag = {"object": {"type": "commit", "sha": SHA}}

    def command(self, args: list[str], **kwargs: object):
        if args[0] == "gh":
            if args[1:3] == ["attestation", "verify"]:
                return b"{}"
            if args[1] == "api":
                endpoint = args[2]
                if "PATCH" in args:
                    assert endpoint.endswith(f"/releases/{self.release['id']}")
                    self.writes.append(args)
                    self.release["draft"] = False
                    return json.dumps(self.release).encode()
                if "/git/ref/" in endpoint:
                    return json.dumps(self.tag).encode()
                if "/git/tags/" in endpoint:
                    return json.dumps(
                        {"object": {"type": "commit", "sha": SHA}}
                    ).encode()
                if "/releases/tags/" in endpoint:
                    return json.dumps(self.release).encode()
                if endpoint.endswith("/releases"):
                    return json.dumps([[self.release]]).encode()
                if "/releases/assets/" in endpoint:
                    asset_id = int(endpoint.rsplit("/", 1)[1])
                    name = next(
                        asset["name"]
                        for asset in self.release["assets"]
                        if asset["id"] == asset_id
                    )
                    return (self.inputs[0] / name).read_bytes()
            if args[1:3] == ["release", "upload"]:
                self.writes.append(args)
                for filename in args[4:]:
                    if (
                        filename.startswith("--")
                        or filename == ENV["GITHUB_REPOSITORY"]
                    ):
                        continue
                    file = Path(filename)
                    self.release["assets"].append(
                        {
                            "id": 99,
                            "name": file.name,
                            "digest": "sha256:"
                            + hashlib.sha256(file.read_bytes()).hexdigest(),
                        }
                    )
                return b""
            if args[1:3] == ["release", "edit"]:
                self.writes.append(args)
                self.release["draft"] = False
                return b""
        if args[:4] == ["docker", "buildx", "imagetools", "inspect"]:
            ref = args[4]
            if "--format" in args and "{{json .Manifest}}" in args:
                return json.dumps({"digest": "sha256:" + "d" * 64}).encode()
            if ref.endswith("@sha256:" + "d" * 64):
                return json.dumps(
                    {
                        "manifests": [
                            {
                                "digest": digest,
                                "platform": {"os": "linux", "architecture": arch},
                            }
                            for arch, digest in DIGESTS.items()
                        ]
                    }
                ).encode()
            if "@" in ref:
                arch = next(
                    arch for arch, digest in DIGESTS.items() if ref.endswith(digest)
                )
                if "--format" in args:
                    return json.dumps({"architecture": arch, "os": "linux"}).encode()
                return b'{"schemaVersion":2,"config":{},"layers":[]}'
            if ref not in self.tags:
                raise publication.CommandError(
                    "Docker", "manifest unknown", missing=True
                )
            return json.dumps(self.tags[ref]).encode()
        if args[:4] == ["docker", "buildx", "imagetools", "create"]:
            self.writes.append(args)
            target = args[args.index("--tag") + 1]
            self.tags[target] = {
                "manifests": [
                    {
                        "digest": digest,
                        "platform": {"os": "linux", "architecture": arch},
                    }
                    for arch, digest in DIGESTS.items()
                ]
            }
            return b""
        raise AssertionError(args)

    def installed_tags(self):
        for registry in REGISTRIES:
            for tag in ("2.2.0", SHA):
                self.tags[f"{registry}:{tag}"] = {
                    "manifests": [
                        {
                            "digest": digest,
                            "platform": {"os": "linux", "architecture": arch},
                        }
                        for arch, digest in DIGESTS.items()
                    ]
                }


def service_patches(service: Services):
    def fetch(version: str):
        return service.pypi

    return patch.object(
        publication, "run_command", side_effect=service.command
    ), patch.object(publication, "fetch_pypi", side_effect=fetch)


@pytest.mark.parametrize("count", [0, 2, 4], ids=["first", "partial", "complete"])
def test_draft_prepare_only_uploads_missing_assets(inputs: Inputs, count: int):
    service = Services(inputs, asset_count=count)
    command, pypi = service_patches(service)
    with command, pypi:
        result = publisher(inputs).prepare()
    assert result == {"pypi_upload": True, "already_published": False}
    assert len(service.release["assets"]) == 4
    assert inputs[3].exists()
    assert not any("edit" in args for args in service.writes)
    assert len(service.writes) == (0 if count == 4 else 1)


def test_promote_and_finalize_verify_every_destination(inputs: Inputs):
    service = Services(inputs)
    command, pypi = service_patches(service)
    with command, pypi:
        publisher(inputs).prepare()
        service.pypi = pypi_files(inputs[1])
        publisher(inputs).promote()
        publisher(inputs).finalize()
    assert not service.release["draft"]
    assert len([args for args in service.writes if "create" in args]) == 6
    edits = [args for args in service.writes if "PATCH" in args]
    assert len(edits) == 1 and edits[0][-1:] == ["make_latest=true"]
    assert service.release["body"] == "Release notes"


def test_published_rerun_verifies_without_writes(inputs: Inputs):
    service = Services(inputs, draft=False, asset_count=4, uploaded=True)
    service.installed_tags()
    command, pypi = service_patches(service)
    with command, pypi:
        assert publisher(inputs).prepare() == {
            "pypi_upload": False,
            "already_published": True,
        }
        publisher(inputs).promote()
        publisher(inputs).finalize()
    assert service.writes == []


@pytest.mark.parametrize(
    "case",
    ["hash", "missing", "sha", "notes", "tag"],
    ids=["hash", "missing", "sha", "notes", "tag"],
)
def test_github_conflicts_stop_before_writes(inputs: Inputs, case: str):
    service = Services(inputs, draft=case != "missing", asset_count=4, uploaded=True)
    service.installed_tags()
    if case == "hash":
        service.release["assets"][0]["digest"] = "sha256:" + "f" * 64
    elif case == "missing":
        service.release["assets"].pop()
    elif case == "sha":
        service.tag["object"]["sha"] = "d" * 40
    elif case == "notes":
        service.release["body"] = " "
    else:
        service.release["tag_name"] = "v2.1.0"
    command, pypi = service_patches(service)
    with command, pypi, pytest.raises(publication.PublicationError):
        publisher(inputs).prepare()
    assert service.writes == []


def test_annotated_tag_and_legacy_asset_digest(inputs: Inputs):
    service = Services(inputs, asset_count=4)
    service.tag["object"] = {"type": "tag", "sha": "e" * 40}
    for asset in service.release["assets"]:
        asset.pop("digest")
    command, pypi = service_patches(service)
    with command, pypi:
        publisher(inputs).prepare()
    assert service.writes == []


@pytest.mark.parametrize(
    "case",
    ["extra", "version", "metadata", "refs", "arch"],
    ids=["extra", "version", "metadata", "refs", "arch"],
)
def test_local_inputs_are_strict(inputs: Inputs, case: str):
    if case == "extra":
        (inputs[0] / "extra.zip").write_bytes(b"extra")
    elif case == "version":
        file = next(inputs[1].glob("*.whl"))
        file.rename(file.with_name(file.name.replace("2.2.0", "2.1.0")))
    elif case == "metadata":
        with zipfile.ZipFile(next(inputs[1].glob("*.whl")), "w") as wheel:
            wheel.writestr(
                "ledfx-2.2.0.dist-info/METADATA", "Name: ledfx\nVersion: 2.1.0\n"
            )
    elif case == "refs":
        (inputs[2] / "docker-amd64.txt").write_text(REGISTRIES[0] + "@sha256:bad")
    else:
        (inputs[2] / "docker-ppc64.txt").write_text("bad")
    with pytest.raises(publication.PublicationError):
        publisher(inputs).prepare()


@pytest.mark.parametrize(
    "case", ["partial", "exact", "conflict"], ids=["partial", "exact", "conflict"]
)
def test_pypi_preflight(inputs: Inputs, case: str):
    service = Services(inputs, uploaded=True)
    if case == "partial":
        service.pypi["urls"].pop()
    elif case == "conflict":
        service.pypi["urls"][0]["digests"]["sha256"] = "f" * 64
    command, pypi = service_patches(service)
    with command, pypi:
        if case == "conflict":
            with pytest.raises(publication.PublicationError):
                publisher(inputs).prepare()
            assert service.writes == []
        else:
            assert publisher(inputs).prepare()["pypi_upload"] is (case == "partial")


@pytest.mark.parametrize("code", [404, 401, 500], ids=["missing", "auth", "server"])
def test_pypi_http_errors_are_not_all_absence(code: int):
    error = HTTPError("https://pypi.org", code, "secret-token", Message(), None)
    with patch.object(publication, "urlopen", side_effect=error):
        if code == 404:
            assert publication.fetch_pypi("2.2.0") is None
        else:
            with pytest.raises(publication.PublicationError, match=f"HTTP {code}"):
                publication.fetch_pypi("2.2.0")


def test_pypi_transport_error_is_redacted():
    with (
        patch.object(publication, "urlopen", side_effect=URLError("secret-token")),
        pytest.raises(publication.PublicationError, match="request failed"),
    ):
        publication.fetch_pypi("2.2.0")


@pytest.mark.parametrize(
    "case", ["conflict", "platform", "auth"], ids=["conflict", "platform", "auth"]
)
def test_docker_preflight_conflicts_are_fatal(inputs: Inputs, case: str):
    service = Services(inputs)
    service.installed_tags()
    if case == "conflict":
        service.tags[f"{REGISTRIES[0]}:2.2.0"]["manifests"][0]["digest"] = (
            "sha256:" + "f" * 64
        )
    original = service.command

    def command(args: list[str], **kwargs: object):
        if case == "auth" and args[0] == "docker":
            raise publication.CommandError("Docker", "request failed", missing=False)
        if case == "platform" and "--format" in args:
            return b'{"architecture":"ppc64le","os":"linux"}'
        return original(args, **kwargs)

    with (
        patch.object(publication, "run_command", side_effect=command),
        patch.object(publication, "fetch_pypi", return_value=service.pypi),
        pytest.raises(publication.PublicationError),
    ):
        publisher(inputs).prepare()
    assert service.writes == []


@pytest.mark.parametrize(
    "stderr,missing",
    [
        (b"manifest unknown", True),
        (b"unauthorized secret-token", False),
        (b"connection refused", False),
    ],
    ids=["missing", "auth", "network"],
)
def test_command_errors_are_redacted_and_classified(stderr: bytes, missing: bool):
    result = subprocess.CompletedProcess(["docker"], 1, b"", stderr)
    with (
        patch.object(publication.subprocess, "run", return_value=result) as run,
        pytest.raises(publication.CommandError) as error,
    ):
        publication.run_command(
            ["docker", "buildx", "imagetools", "inspect", "image:tag", "--raw"]
        )
    assert error.value.missing is missing
    assert "secret-token" not in str(error.value)
    assert run.call_args.kwargs["timeout"] > 0
    assert not run.call_args.kwargs.get("shell", False)


def test_snapshot_rejects_changed_local_inputs(inputs: Inputs):
    service = Services(inputs)
    command, pypi = service_patches(service)
    with command, pypi:
        publisher(inputs).prepare()
        next(inputs[0].iterdir()).write_bytes(b"changed")
        with pytest.raises(publication.PublicationError, match="snapshot"):
            publisher(inputs).promote()


def test_attestation_failure_prevents_publication(inputs: Inputs):
    service = Services(inputs, asset_count=4, uploaded=True)
    original = service.command

    def command(args: list[str], **kwargs: object):
        if args[1:3] == ["attestation", "verify"]:
            raise publication.CommandError("GitHub", "verification failed")
        return original(args, **kwargs)

    with (
        patch.object(publication, "run_command", side_effect=command),
        patch.object(publication, "fetch_pypi", return_value=service.pypi),
    ):
        publisher(inputs).prepare()
        publisher(inputs).promote()
        with pytest.raises(publication.PublicationError):
            publisher(inputs).finalize()
    assert service.release["draft"]
    assert not any("edit" in args for args in service.writes)


def test_promote_exposes_manifest_digests_and_finalization_checks_provenance(
    inputs: Inputs,
):
    service = Services(inputs, asset_count=4, uploaded=True)
    command, pypi = service_patches(service)
    with command as calls, pypi:
        publisher(inputs).prepare()
        assert publisher(inputs).promote() == {
            "ghcr_digest": "sha256:" + "d" * 64,
            "dockerhub_digest": "sha256:" + "d" * 64,
        }
        publisher(inputs).finalize()
    verifications = [
        call.args[0]
        for call in calls.call_args_list
        if call.args[0][1:3] == ["attestation", "verify"]
    ]
    assert len(verifications) == 8
    for args in verifications:
        assert args[args.index("--source-digest") + 1] == SHA
        assert args[args.index("--source-ref") + 1] == "refs/tags/" + TAG
        assert (
            args[args.index("--signer-workflow") + 1]
            == "LedFx/LedFx/.github/workflows/ci.yml"
        )
        assert "--deny-self-hosted-runners" in args


def test_prepare_reuses_immutable_snapshot_after_publication(inputs: Inputs):
    service = Services(inputs, asset_count=4, uploaded=True)
    command, pypi = service_patches(service)
    with command, pypi:
        publisher(inputs).prepare()
        original_snapshot = inputs[3].read_bytes()
        publisher(inputs).promote()
        publisher(inputs).finalize()
        service.writes.clear()
        assert publisher(inputs).prepare()["already_published"] is True
    assert inputs[3].read_bytes() == original_snapshot
    assert service.writes == []


def test_cli_writes_prepare_outputs(inputs: Inputs, tmp_path: Path):
    import os

    service = Services(inputs)
    command, pypi = service_patches(service)
    output = tmp_path / "output"
    with (
        command,
        pypi,
        patch.dict(os.environ, {**ENV, "GITHUB_OUTPUT": str(output)}, clear=True),
    ):
        assert (
            publication.main(
                [
                    "prepare",
                    "--assets",
                    str(inputs[0]),
                    "--dist",
                    str(inputs[1]),
                    "--docker-digests",
                    str(inputs[2]),
                    "--snapshot",
                    str(inputs[3]),
                ]
            )
            == 0
        )
    assert output.read_text() == "pypi_upload=true\nalready_published=false\n"


def test_publication_latest_value_is_a_string_api_field(inputs: Inputs):
    service = Services(inputs, asset_count=4, uploaded=True)
    command, pypi = service_patches(service)
    with command, pypi:
        publisher(inputs).prepare()
        publisher(inputs).promote()
        publisher(inputs).finalize()
    edit = next(args for args in service.writes if "PATCH" in args)
    assert edit[-2:] == ["-f", "make_latest=true"]


def test_published_snapshot_rerun_allows_newer_release(inputs: Inputs):
    service = Services(inputs, draft=False, asset_count=4, uploaded=True)
    service.installed_tags()
    original = service.command
    newer = {"tag_name": "v3.0.0", "draft": False, "prerelease": False}
    command, pypi = service_patches(service)
    with command, pypi:
        publisher(inputs).prepare()
    snapshot = inputs[3].read_bytes()

    def command_with_newer(args: list[str], **kwargs: object):
        if args[:3] == ["gh", "api", "repos/LedFx/LedFx/releases"]:
            return json.dumps([[service.release, newer]]).encode()
        return original(args, **kwargs)

    with patch.object(publication, "run_command", side_effect=command_with_newer), pypi:
        assert publisher(inputs).prepare()["already_published"] is True
    assert inputs[3].read_bytes() == snapshot
    assert service.writes == []


@pytest.mark.parametrize("target", ["release", "tag"], ids=["release", "tag"])
def test_remote_missing_is_fatal_and_never_created(inputs: Inputs, target: str):
    service = Services(inputs)
    original = service.command

    def command(args: list[str], **kwargs: object):
        if (
            args[0] == "gh"
            and args[1] == "api"
            and (
                (target == "release" and "/releases/tags/" in args[2])
                or (target == "tag" and "/git/ref/" in args[2])
            )
        ):
            raise publication.CommandError("GitHub", "artifact absent", missing=True)
        return original(args, **kwargs)

    with (
        patch.object(publication, "run_command", side_effect=command),
        patch.object(publication, "fetch_pypi", return_value=None),
        pytest.raises(publication.PublicationError),
    ):
        publisher(inputs).prepare()
    assert service.writes == []


def test_source_indices_resolve_platform_children(inputs: Inputs):
    service = Services(inputs)
    original = service.command

    def command(args: list[str], **kwargs: object):
        if args[0] == "docker" and "@" in args[4] and "--raw" in args:
            arch = next(
                arch for arch, digest in DIGESTS.items() if args[4].endswith(digest)
            )
            return json.dumps(
                {
                    "manifests": [
                        {
                            "digest": DIGESTS[arch],
                            "platform": {"os": "linux", "architecture": arch},
                        },
                        {
                            "digest": "sha256:" + "f" * 64,
                            "platform": {"os": "unknown", "architecture": "unknown"},
                        },
                    ]
                }
            ).encode()
        return original(args, **kwargs)

    with (
        patch.object(publication, "run_command", side_effect=command),
        patch.object(publication, "fetch_pypi", return_value=None),
    ):
        publisher(inputs).prepare()
    snapshot = json.loads(inputs[3].read_text())
    assert snapshot["children"] == {image: DIGESTS for image in REGISTRIES}


def test_complete_rerun_skips_existing_docker_immutable_tags(inputs: Inputs):
    service = Services(inputs, asset_count=4, uploaded=True)
    service.installed_tags()
    command, pypi = service_patches(service)
    with command, pypi:
        publisher(inputs).prepare()
        publisher(inputs).promote()
    assert len(service.writes) == 2
    assert all(
        args[args.index("--tag") + 1].endswith(":latest") for args in service.writes
    )


def test_pypi_propagation_is_bounded(inputs: Inputs):
    service = Services(inputs, asset_count=4)
    command, pypi = service_patches(service)
    with command, pypi:
        publisher(inputs).prepare()
    with (
        command,
        patch.object(
            publication,
            "fetch_pypi",
            side_effect=[None, {"urls": []}, pypi_files(inputs[1])],
        ),
        patch.object(publication.time, "sleep") as sleep,
    ):
        publisher(inputs).promote()
    assert sleep.call_count == 2


@pytest.mark.parametrize(
    "case",
    ["body", "pre", "id", "tag", "sha", "asset", "local"],
    ids=["body", "pre", "id", "tag", "sha", "asset", "local"],
)
def test_finalization_rechecks_after_attestations(inputs: Inputs, case: str):
    service = Services(inputs, asset_count=4, uploaded=True)
    command, pypi = service_patches(service)
    with command, pypi:
        publisher(inputs).prepare()
        publisher(inputs).promote()
    service.writes.clear()
    original = service.command

    def mutate(args: list[str], **kwargs: object):
        if args[1:3] == ["attestation", "verify"]:
            if case == "body":
                service.release["body"] = "Changed release notes"
            elif case == "pre":
                service.release["prerelease"] = True
            elif case == "id":
                service.release["id"] = 43
            elif case == "tag":
                service.release["tag_name"] = "v2.3.0"
            elif case == "sha":
                service.tag["object"]["sha"] = "f" * 40
            elif case == "asset":
                service.release["assets"][0]["digest"] = "sha256:" + "f" * 64
            else:
                next(inputs[0].iterdir()).write_bytes(b"changed after verification")
        return original(args, **kwargs)

    with (
        patch.object(publication, "run_command", side_effect=mutate),
        pypi,
        pytest.raises(publication.PublicationError),
    ):
        publisher(inputs).finalize()
    assert service.release["draft"]
    assert service.writes == []


def test_publication_targets_snapshot_id_and_only_changes_publication_flags(
    inputs: Inputs,
):
    service = Services(inputs, asset_count=4, uploaded=True)
    command, pypi = service_patches(service)
    with command, pypi:
        publisher(inputs).prepare()
        publisher(inputs).promote()
        publisher(inputs).finalize()
    publish = service.writes[-1]
    assert publish[:3] == ["gh", "api", "repos/LedFx/LedFx/releases/42"]
    assert publish[3:] == [
        "--method",
        "PATCH",
        "-F",
        "draft=false",
        "-f",
        "make_latest=true",
    ]


def test_dockerhub_attestation_uses_canonical_registry_subject(inputs: Inputs):
    service = Services(inputs, asset_count=4, uploaded=True)
    command, pypi = service_patches(service)
    with command as calls, pypi:
        publisher(inputs).prepare()
        publisher(inputs).promote()
        publisher(inputs).finalize()
    subjects = [
        call.args[0][3]
        for call in calls.call_args_list
        if call.args[0][1:3] == ["attestation", "verify"]
    ]
    assert "oci://docker.io/ledfxorg/ledfx@sha256:" + "d" * 64 in subjects


@pytest.mark.parametrize(
    "phase", ["prepare", "promote", "latest"], ids=["prepare", "promote", "latest"]
)
def test_each_write_phase_rechecks_metadata_after_slow_reads(
    inputs: Inputs, phase: str
):
    service = Services(
        inputs, asset_count=0 if phase == "prepare" else 4, uploaded=True
    )
    command, pypi = service_patches(service)
    if phase != "prepare":
        with command, pypi:
            publisher(inputs).prepare()
    service.writes.clear()
    original = service.command

    def mutate(args: list[str], **kwargs: object):
        if phase == "latest" and args[:3] == [
            "gh",
            "api",
            "repos/LedFx/LedFx/releases",
        ]:
            service.release["body"] = "Changed during latest lookup"
        if (
            phase != "latest"
            and args[:4] == ["docker", "buildx", "imagetools", "inspect"]
            and "@" not in args[4]
        ):
            service.release["body"] = "Changed during registry lookup"
        return original(args, **kwargs)

    with (
        patch.object(publication, "run_command", side_effect=mutate),
        pypi,
        pytest.raises(publication.PublicationError),
    ):
        getattr(publisher(inputs), "prepare" if phase == "prepare" else "promote")()
    if phase == "latest":
        assert all(
            not args[args.index("--tag") + 1].endswith(":latest")
            for args in service.writes
        )
    else:
        assert service.writes == []


def test_release_becoming_public_during_promote_requires_all_immutable_tags(
    inputs: Inputs,
):
    service = Services(inputs, asset_count=4, uploaded=True)
    service.installed_tags()
    for image in REGISTRIES:
        del service.tags[f"{image}:{SHA}"]
    command, pypi = service_patches(service)
    with command, pypi:
        publisher(inputs).prepare()
    original = service.command

    def became_public(args: list[str], **kwargs: object):
        if (
            args[:4] == ["docker", "buildx", "imagetools", "inspect"]
            and args[4] == f"{REGISTRIES[0]}:2.2.0"
            and "--raw" in args
        ):
            service.release["draft"] = False
        return original(args, **kwargs)

    with (
        patch.object(publication, "run_command", side_effect=became_public),
        pypi,
        pytest.raises(publication.PublicationError),
    ):
        publisher(inputs).promote()
    assert service.writes == []


def test_prepare_does_not_redownload_legacy_assets_after_final_identity_check(
    inputs: Inputs,
):
    service = Services(inputs, asset_count=2, uploaded=True)
    for asset in service.release["assets"]:
        asset.pop("digest")
    original = service.command
    tag_checks = 0

    def command(args: list[str], **kwargs: object):
        nonlocal tag_checks
        if args[:2] == ["gh", "api"] and "/git/ref/" in args[2]:
            tag_checks += 1
        if (
            args[:2] == ["gh", "api"]
            and "/releases/assets/" in args[2]
            and tag_checks >= 3
            and not service.writes
        ):
            service.release["body"] = "Changed during a redundant download"
        return original(args, **kwargs)

    with (
        patch.object(publication, "run_command", side_effect=command),
        patch.object(publication, "fetch_pypi", return_value=service.pypi),
    ):
        publisher(inputs).prepare()
    assert service.release["body"] == "Release notes"
    assert len(service.writes) == 1


@pytest.mark.parametrize(
    "ref,stderr,missing",
    [
        (
            "ghcr.io/ledfx/ledfx:2.2.0",
            b"ERROR: ghcr.io/ledfx/ledfx:2.2.0: not found\n",
            True,
        ),
        (
            "ledfxorg/ledfx:2.2.0",
            b"ERROR: docker.io/ledfxorg/ledfx:2.2.0: not found\n",
            True,
        ),
        ("ledfxorg/ledfx:2.2.0", b"ERROR: ledfxorg/ledfx:2.2.0: not found\n", True),
        ("ledfxorg/ledfx:2.2.0", b"ERROR: other/image:2.2.0: not found\n", False),
        ("ledfxorg/ledfx:2.2.0", b"ERROR: not found\n", False),
        ("ledfxorg/ledfx:2.2.0", b"docker: executable not found", False),
        (
            "ledfxorg/ledfx:2.2.0",
            b"ERROR: docker.io/ledfxorg/ledfx:2.2.0: unauthorized",
            False,
        ),
        (
            "ledfxorg/ledfx:2.2.0",
            b"ERROR: docker.io/ledfxorg/ledfx:2.2.0: connection refused",
            False,
        ),
    ],
    ids=[
        "ghcr",
        "canonical",
        "requested",
        "other",
        "generic",
        "executable",
        "auth",
        "transport",
    ],
)
def test_real_buildx_missing_classification_boundary(
    inputs: Inputs, ref: str, stderr: bytes, missing: bool
):
    result = subprocess.CompletedProcess(["docker"], 1, b"", stderr)
    with patch.object(publication.subprocess, "run", return_value=result):
        if missing:
            assert publisher(inputs).inspect(ref, "--raw", allow_missing=True) is None
        else:
            with pytest.raises(publication.CommandError) as error:
                publisher(inputs).inspect(ref, "--raw", allow_missing=True)
            assert error.value.missing is False


def test_ref_not_found_does_not_classify_creation_failure_as_absent():
    result = subprocess.CompletedProcess(
        ["docker"], 1, b"", b"ERROR: ghcr.io/ledfx/ledfx:2.2.0: not found\n"
    )
    with (
        patch.object(publication.subprocess, "run", return_value=result),
        pytest.raises(publication.CommandError) as error,
    ):
        publication.run_command(
            [
                "docker",
                "buildx",
                "imagetools",
                "create",
                "--tag",
                "ghcr.io/ledfx/ledfx:2.2.0",
            ]
        )
    assert error.value.missing is False


@pytest.mark.parametrize("conflict", [True, False], ids=["conflict", "matching"])
def test_promote_reinspects_missing_tags_after_slow_recheck(
    inputs: Inputs, conflict: bool
):
    service = Services(inputs, asset_count=4, uploaded=True)
    command, pypi = service_patches(service)
    with command, pypi:
        publisher(inputs).prepare()
    original = service.command
    missing_was_read = False
    appeared = False
    ref = f"{REGISTRIES[0]}:2.2.0"

    def command(args: list[str], **kwargs: object):
        nonlocal missing_was_read, appeared
        if (
            args[:4] == ["docker", "buildx", "imagetools", "inspect"]
            and args[4] == ref
            and "--raw" in args
        ):
            missing_was_read = True
        if (
            missing_was_read
            and not appeared
            and args[:2] == ["gh", "api"]
            and "/releases/tags/" in args[2]
        ):
            appeared = True
            service.tags[ref] = {
                "manifests": [
                    {
                        "digest": "sha256:" + "f" * 64
                        if conflict and arch == "amd64"
                        else digest,
                        "platform": {"os": "linux", "architecture": arch},
                    }
                    for arch, digest in DIGESTS.items()
                ]
            }
        return original(args, **kwargs)

    with patch.object(publication, "run_command", side_effect=command), pypi:
        if conflict:
            with pytest.raises(publication.PublicationError):
                publisher(inputs).promote()
            assert service.writes == []
        else:
            publisher(inputs).promote()
            assert all(args[args.index("--tag") + 1] != ref for args in service.writes)


def test_prepare_rehashes_missing_archive_after_legacy_downloads(inputs: Inputs):
    service = Services(inputs, asset_count=2, uploaded=True)
    for asset in service.release["assets"]:
        asset.pop("digest")
    existing = {asset["name"] for asset in service.release["assets"]}
    missing = next(path for path in inputs[0].iterdir() if path.name not in existing)
    original = service.command
    downloads = 0

    def command(args: list[str], **kwargs: object):
        nonlocal downloads
        if args[:2] == ["gh", "api"] and "/releases/assets/" in args[2]:
            downloads += 1
            if downloads == 3:
                missing.write_bytes(b"modified while remote asset downloaded")
        return original(args, **kwargs)

    with (
        patch.object(publication, "run_command", side_effect=command),
        patch.object(publication, "fetch_pypi", return_value=service.pypi),
        pytest.raises(publication.PublicationError),
    ):
        publisher(inputs).prepare()
    assert service.writes == []
