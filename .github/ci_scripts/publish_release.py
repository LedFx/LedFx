"""Verify staged artifacts before publishing the existing release-please draft.

Run prepare, promote, then finalize with the same inputs and snapshot. GitHub
operations use gh (and GH_TOKEN), registries use docker buildx, PyPI uses urllib.
No release, tag, or asset is ever replaced. A published rerun only verifies.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import time
import zipfile
from email.parser import Parser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

STABLE = re.compile(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\Z")
VERSION = re.compile(r"v(\d+\.\d+\.\d+(?:[ab]\d+|rc\d+|-(?:alpha|beta|rc)\.\d+)?)\Z")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")


class PublicationError(RuntimeError):
    """A concise, credential-free publication failure."""


class CommandError(PublicationError):
    def __init__(self, service: str, message: str, missing: bool = False):
        super().__init__(f"{service}: {message}")
        self.missing = missing


def run_command(args: list[str]) -> bytes:
    service = "GitHub" if args[0] == "gh" else "Docker"
    try:
        result = subprocess.run(args, capture_output=True, timeout=180, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise CommandError(service, "command failed or timed out") from None
    if result.returncode:
        # Only explicit server absence qualifies. Auth, DNS, rate limiting and
        # arbitrary CLI failures must not be mistaken for an absent artifact.
        stderr = result.stderr.decode("utf-8", errors="replace").lower()
        missing = bool(
            re.search(r"\bhttp 404\b|\bmanifest unknown\b|\bmanifest_unknown\b", stderr)
        )
        if args[:4] == ["docker", "buildx", "imagetools", "inspect"] and len(args) > 4:
            ref = args[4].lower()
            refs = {ref}
            registry = ref.split("/", 1)[0]
            if "/" not in ref:
                refs.add(f"docker.io/library/{ref}")
            elif (
                "." not in registry and ":" not in registry and registry != "localhost"
            ):
                refs.add(f"docker.io/{ref}")
            # containerd's HEAD 404 wraps ErrNotFound with the exact resolved
            # reference. Generic 'not found' (or another reference) is fatal.
            message = stderr.strip().removeprefix("error:").strip()
            missing = missing or message in {f"{ref}: not found" for ref in refs}
        raise CommandError(
            service, "artifact absent" if missing else "command failed", missing
        )
    return result.stdout


def decode_json(data: bytes, service: str):
    try:
        return json.loads(data)
    except (ValueError, UnicodeError):
        raise PublicationError(f"{service} returned invalid JSON") from None


def fetch_pypi(version: str):
    request = Request(
        f"https://pypi.org/pypi/ledfx/{version}/json",
        headers={"User-Agent": "LedFx-release-publication"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            return decode_json(response.read(), "PyPI")
    except HTTPError as error:
        if error.code == 404:
            return None
        raise PublicationError(f"PyPI returned HTTP {error.code}") from None
    except (URLError, TimeoutError, OSError):
        raise PublicationError("PyPI request failed or timed out") from None


def should_promote_latest(tag: str, prerelease: bool, releases: list[dict]) -> bool:
    match = STABLE.fullmatch(tag)
    if prerelease or not match:
        return False
    version = tuple(map(int, match.groups()))
    for release in releases:
        if release.get("draft") or release.get("prerelease"):
            continue
        other = STABLE.fullmatch(release.get("tag_name", ""))
        if other and tuple(map(int, other.groups())) > version:
            return False
    return True


def sha256(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def directory_files(directory: Path) -> dict[str, Path]:
    if not directory.is_dir():
        raise PublicationError("Artifact directory is missing")
    paths = list(directory.iterdir())
    if any(not path.is_file() or path.is_symlink() for path in paths):
        raise PublicationError("Artifact directory must contain only regular files")
    return {path.name: path for path in paths}


class Publisher:
    def __init__(
        self,
        assets: Path,
        dist: Path,
        docker_digests: Path,
        snapshot: Path,
        environment=None,
    ):
        environment = os.environ if environment is None else environment
        required = (
            "GITHUB_REPOSITORY",
            "GITHUB_REF_NAME",
            "GITHUB_SHA",
            "GH_TOKEN",
            "GHCR_IMAGE",
            "DOCKERHUB_IMAGE",
        )
        if any(not environment.get(key) for key in required):
            raise PublicationError("Required publication environment is missing")
        self.repo = environment["GITHUB_REPOSITORY"]
        self.tag = environment["GITHUB_REF_NAME"]
        self.sha = environment["GITHUB_SHA"]
        self.images = [environment["GHCR_IMAGE"], environment["DOCKERHUB_IMAGE"]]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self.repo):
            raise PublicationError("Invalid repository")
        if not VERSION.fullmatch(self.tag) or not re.fullmatch(
            r"[0-9a-f]{40}", self.sha
        ):
            raise PublicationError("Invalid release tag or source SHA")
        if self.images != ["ghcr.io/ledfx/ledfx", "ledfxorg/ledfx"]:
            raise PublicationError("Unexpected release registries")
        self.version = self.tag[1:]
        self.pypi_version = re.sub(
            r"-(alpha|beta|rc)\.(\d+)",
            lambda match: {"alpha": "a", "beta": "b", "rc": "rc"}[match[1]] + match[2],
            self.version,
        )
        self.assets_dir, self.dist_dir, self.docker_dir = assets, dist, docker_digests
        self.snapshot_path = snapshot

    def api(self, endpoint: str, *options: str):
        return decode_json(
            run_command(["gh", "api", f"repos/{self.repo}/{endpoint}", *options]),
            "GitHub",
        )

    def release(self):
        release = self.api(f"releases/tags/{self.tag}")
        if not isinstance(release, dict) or release.get("tag_name") != self.tag:
            raise PublicationError("GitHub release tag does not match")
        if not isinstance(release.get("draft"), bool) or not isinstance(
            release.get("prerelease"), bool
        ):
            raise PublicationError("GitHub release flags are missing")
        if not isinstance(release.get("body"), str) or not release["body"].strip():
            raise PublicationError("GitHub release notes are empty")
        if not isinstance(release.get("id"), int) or not isinstance(
            release.get("assets"), list
        ):
            raise PublicationError("GitHub release metadata is incomplete")
        ref = self.api(f"git/ref/tags/{self.tag}")
        for _ in range(10):
            obj = ref.get("object", {})
            if obj.get("type") == "commit":
                if obj.get("sha") != self.sha:
                    raise PublicationError(
                        "Remote release tag source SHA does not match"
                    )
                return release
            if obj.get("type") != "tag" or not re.fullmatch(
                r"[0-9a-f]{40}", obj.get("sha", "")
            ):
                break
            ref = self.api(f"git/tags/{obj['sha']}")
        raise PublicationError("Remote release tag does not resolve to a commit")

    def local_inputs(self):
        assets = directory_files(self.assets_dir)
        expected = {
            f"LedFx-{self.version}-{suffix}"
            for suffix in (
                "win-x64.zip",
                "win-x64-setup.zip",
                "osx-arm64.tar.gz",
                "osx-intel.tar.gz",
            )
        }
        if set(assets) != expected:
            raise PublicationError(
                "Release archives do not match the expected four filenames/version"
            )
        dist = directory_files(self.dist_dir)
        wheels = [
            name
            for name in dist
            if re.fullmatch(
                rf"[Ll]ed[Ff]x-{re.escape(self.pypi_version)}-[A-Za-z0-9_.]+-[A-Za-z0-9_.]+-[A-Za-z0-9_.]+\.whl",
                name,
            )
        ]
        sdists = [
            name for name in dist if name.lower() == f"ledfx-{self.pypi_version}.tar.gz"
        ]
        if len(dist) != 2 or len(wheels) != 1 or len(sdists) != 1:
            raise PublicationError(
                "PyPI distributions must be one wheel and sdist for the tagged version"
            )
        try:
            with zipfile.ZipFile(dist[wheels[0]]) as wheel:
                metadata_names = [
                    name
                    for name in wheel.namelist()
                    if name.endswith(".dist-info/METADATA")
                ]
                if len(metadata_names) != 1:
                    raise PublicationError("Wheel metadata is missing or ambiguous")
                wheel_metadata = wheel.read(metadata_names[0]).decode()
            with tarfile.open(dist[sdists[0]], "r:gz") as archive:
                metadata_members = [
                    member
                    for member in archive.getmembers()
                    if member.name.count("/") == 1
                    and member.name.endswith("/PKG-INFO")
                    and member.isfile()
                ]
                if len(metadata_members) != 1:
                    raise PublicationError("Sdist metadata is missing or ambiguous")
                file = archive.extractfile(metadata_members[0])
                if file is None:
                    raise PublicationError("Sdist metadata is missing")
                with file:
                    sdist_metadata = file.read().decode()
            for metadata in (wheel_metadata, sdist_metadata):
                parsed = Parser().parsestr(metadata)
                if (
                    parsed["Version"] != self.pypi_version
                    or (parsed["Name"] or "").lower() != "ledfx"
                ):
                    raise PublicationError(
                        "Distribution metadata version/name does not match"
                    )
        except (
            OSError,
            ValueError,
            UnicodeError,
            zipfile.BadZipFile,
            tarfile.TarError,
        ):
            raise PublicationError("Distribution archive is invalid") from None
        files = directory_files(self.docker_dir)
        if set(files) != {"docker-amd64.txt", "docker-arm64.txt"}:
            raise PublicationError("Docker inputs must contain exactly amd64 and arm64")
        sources = {image: {} for image in self.images}
        for arch in ("amd64", "arm64"):
            refs = files[f"docker-{arch}.txt"].read_text().split()
            if len(refs) != 2:
                raise PublicationError(
                    "Docker architecture needs exactly two registry digest references"
                )
            seen = set()
            for ref in refs:
                image, separator, digest = ref.partition("@")
                if (
                    separator != "@"
                    or image not in self.images
                    or image in seen
                    or not DIGEST.fullmatch(digest)
                ):
                    raise PublicationError(
                        "Docker digest reference is invalid or duplicated"
                    )
                seen.add(image)
                sources[image][arch] = ref
        return {
            "assets": {name: sha256(path) for name, path in assets.items()},
            "dist": {name: sha256(path) for name, path in dist.items()},
            "sources": sources,
        }

    def verify_assets(self, release, hashes, complete=False):
        remote = {}
        for asset in release["assets"]:
            name = asset.get("name")
            if name in remote or name not in hashes:
                raise PublicationError(
                    "GitHub release contains unexpected or duplicate assets"
                )
            remote[name] = asset
            digest = asset.get("digest")
            if digest:
                if digest != "sha256:" + hashes[name]:
                    raise PublicationError(
                        "GitHub asset checksum conflicts with tested archive"
                    )
            else:
                data = run_command(
                    [
                        "gh",
                        "api",
                        f"repos/{self.repo}/releases/assets/{asset['id']}",
                        "-H",
                        "Accept: application/octet-stream",
                    ]
                )
                if hashlib.sha256(data).hexdigest() != hashes[name]:
                    raise PublicationError(
                        "GitHub asset checksum conflicts with tested archive"
                    )
        missing = set(hashes) - set(remote)
        if missing and (complete or not release["draft"]):
            raise PublicationError("GitHub release archives are incomplete")
        return sorted(missing)

    def verify_pypi(self, hashes, complete=False):
        for attempt in range(3 if complete else 1):
            response = fetch_pypi(self.pypi_version)
            files = [] if response is None else response.get("urls")
            if not isinstance(files, list):
                raise PublicationError("PyPI returned invalid distribution metadata")
            remote = set()
            for file in files:
                name = file.get("filename")
                if (
                    name not in hashes
                    or name in remote
                    or file.get("digests", {}).get("sha256") != hashes[name]
                ):
                    raise PublicationError(
                        "PyPI distribution checksum/files conflict with tested distributions"
                    )
                remote.add(name)
            if remote == set(hashes):
                return True
            if not complete:
                return False
            if attempt < 2:
                time.sleep(2)
        raise PublicationError("PyPI distributions are incomplete")

    def inspect(self, ref, *options, allow_missing=False):
        try:
            return decode_json(
                run_command(
                    ["docker", "buildx", "imagetools", "inspect", ref, *options]
                ),
                "Docker",
            )
        except CommandError as error:
            if error.missing and allow_missing:
                return None
            raise

    def children(self, manifest):
        if not isinstance(manifest, dict) or not isinstance(
            manifest.get("manifests"), list
        ):
            raise PublicationError("Docker tag must be a multi-architecture manifest")
        children = {}
        for descriptor in manifest["manifests"]:
            platform = descriptor.get("platform", {})
            if (
                platform.get("os") == "unknown"
                and platform.get("architecture") == "unknown"
            ):
                continue  # BuildKit provenance descriptor is not a runnable child.
            arch = platform.get("architecture")
            digest = descriptor.get("digest", "")
            if (
                platform.get("os") != "linux"
                or arch not in ("amd64", "arm64")
                or arch in children
                or not DIGEST.fullmatch(digest)
            ):
                raise PublicationError("Docker manifest platforms/digests conflict")
            children[arch] = digest
        return children

    def source_children(self, sources):
        expected = {}
        for image, refs in sources.items():
            expected[image] = {}
            for arch, ref in refs.items():
                raw = self.inspect(ref, "--raw")
                if "manifests" in raw:
                    children = self.children(raw)
                    if set(children) != {arch}:
                        raise PublicationError(
                            "Docker source index does not match its architecture"
                        )
                    digest = children[arch]
                else:
                    config = self.inspect(ref, "--format", "{{json .Image}}")
                    if (
                        config.get("os") != "linux"
                        or config.get("architecture") != arch
                    ):
                        raise PublicationError(
                            "Docker source platform does not match its architecture"
                        )
                    digest = ref.split("@", 1)[1]
                expected[image][arch] = digest
        return expected

    def verify_docker(self, expected, complete=False):
        missing = []
        for image, children in expected.items():
            for tag in (self.version, self.sha):
                ref = f"{image}:{tag}"
                manifest = self.inspect(ref, "--raw", allow_missing=not complete)
                if manifest is None:
                    missing.append(ref)
                elif self.children(manifest) != children:
                    raise PublicationError(
                        "Docker immutable tag conflicts with tested source digests"
                    )
        return missing

    def latest(self, release):
        pages = self.api("releases", "--paginate", "--slurp")
        if not isinstance(pages, list) or any(
            not isinstance(page, list) for page in pages
        ):
            raise PublicationError("GitHub release list is invalid")
        return should_promote_latest(
            self.tag,
            release["prerelease"],
            [release for page in pages for release in page],
        )

    def snapshot(self, release, local, children):
        return {
            "repository": self.repo,
            "tag": self.tag,
            "sha": self.sha,
            "release_id": release["id"],
            "body_sha256": hashlib.sha256(release["body"].encode()).hexdigest(),
            "prerelease": release["prerelease"],
            "already_published": not release["draft"],
            "latest": self.latest(release),
            **local,
            "children": children,
        }

    def load_snapshot(self):
        try:
            snapshot = json.loads(self.snapshot_path.read_text())
        except (OSError, ValueError):
            raise PublicationError(
                "Publication snapshot is missing or invalid"
            ) from None
        local = self.local_inputs()
        release = self.release()
        identity = {
            "repository": self.repo,
            "tag": self.tag,
            "sha": self.sha,
            "release_id": release["id"],
            "body_sha256": hashlib.sha256(release["body"].encode()).hexdigest(),
            "prerelease": release["prerelease"],
            **local,
        }
        if any(snapshot.get(key) != value for key, value in identity.items()):
            raise PublicationError(
                "Publication inputs no longer match immutable snapshot"
            )
        if snapshot["already_published"] and release["draft"]:
            raise PublicationError("Published release unexpectedly became a draft")
        children = self.source_children(local["sources"])
        if children != snapshot["children"]:
            raise PublicationError("Docker sources no longer match snapshot")
        return snapshot, release

    def checked_release(self, snapshot):
        release = self.release()
        identity = {
            "release_id": release["id"],
            "body_sha256": hashlib.sha256(release["body"].encode()).hexdigest(),
            "prerelease": release["prerelease"],
        }
        if any(snapshot.get(key) != value for key, value in identity.items()):
            raise PublicationError(
                "GitHub release no longer matches immutable snapshot"
            )
        if snapshot["already_published"] and release["draft"]:
            raise PublicationError("Published release unexpectedly became a draft")
        return release

    def recheck_before_write(self, snapshot, complete_assets=True):
        # Remote inspections/attestations can take minutes. Check the frozen
        # local bytes and release identity again after those reads, immediately
        # before the write batch. GitHub offers no atomic metadata compare/write.
        release = self.checked_release(snapshot)
        self.verify_assets(release, snapshot["assets"], complete=complete_assets)
        # Legacy asset downloads may themselves take time. Hash local inputs
        # after downloading, so changed missing archives cannot be uploaded.
        local = self.local_inputs()
        if any(snapshot.get(key) != value for key, value in local.items()):
            raise PublicationError(
                "Publication inputs no longer match immutable snapshot"
            )
        return self.checked_release(snapshot)

    def prepare(self):
        local = self.local_inputs()
        release = self.release()
        missing_assets = self.verify_assets(release, local["assets"])
        pypi_complete = self.verify_pypi(local["dist"], complete=not release["draft"])
        children = self.source_children(local["sources"])
        self.verify_docker(children, complete=not release["draft"])
        snapshot = self.snapshot(release, local, children)
        if self.snapshot_path.exists():
            try:
                existing = json.loads(self.snapshot_path.read_text())
            except (OSError, ValueError):
                raise PublicationError("Publication snapshot is invalid") from None
            comparison = dict(snapshot)
            comparison["already_published"] = existing.get("already_published")
            comparison["latest"] = existing.get("latest")
            if existing != comparison or (
                existing.get("already_published") and release["draft"]
            ):
                raise PublicationError(
                    "Publication snapshot already exists with different inputs"
                )
        else:
            with self.snapshot_path.open("x") as file:
                json.dump(snapshot, file, sort_keys=True, indent=2)
        release = self.recheck_before_write(snapshot, complete_assets=False)
        # recheck_before_write already validated every existing asset. Compute
        # the upload set from that checked metadata without another download.
        missing_assets = sorted(
            set(local["assets"]) - {asset["name"] for asset in release["assets"]}
        )
        if not release["draft"]:
            pypi_complete = self.verify_pypi(local["dist"], complete=True)
            self.verify_docker(children, complete=True)
        if missing_assets:
            run_command(
                [
                    "gh",
                    "release",
                    "upload",
                    self.tag,
                    *(str(self.assets_dir / name) for name in missing_assets),
                    "--repo",
                    self.repo,
                ]
            )
            self.verify_assets(self.release(), local["assets"], complete=True)
        return {
            "pypi_upload": not pypi_complete,
            "already_published": not release["draft"],
        }

    def manifest_digests(self, expected):
        digests = {}
        for image in self.images:
            descriptor = self.inspect(
                f"{image}:{self.version}", "--format", "{{json .Manifest}}"
            )
            digest = descriptor.get("digest", "")
            if not DIGEST.fullmatch(digest):
                raise PublicationError(
                    "Docker version manifest descriptor digest is invalid"
                )
            # Verify the exact descriptor to be attested, not just its moving tag.
            if (
                self.children(self.inspect(f"{image}@{digest}", "--raw"))
                != expected[image]
            ):
                raise PublicationError(
                    "Docker version descriptor conflicts with tested source digests"
                )
            digests[image] = digest
        return digests

    def promote(self):
        snapshot, release = self.load_snapshot()
        self.verify_assets(release, snapshot["assets"], complete=True)
        self.verify_pypi(snapshot["dist"], complete=True)
        missing = self.verify_docker(
            snapshot["children"], complete=not release["draft"]
        )
        release = self.recheck_before_write(snapshot)
        if release["draft"]:
            for ref in missing:
                image = ref.rsplit(":", 1)[0]
                release = self.recheck_before_write(snapshot)
                if not release["draft"]:
                    self.verify_docker(snapshot["children"], complete=True)
                    break
                # A tag may appear during the slow release/assets checks. Read
                # it again immediately before creating; do not replace known
                # tags. Registries offer no atomic absent-tag create, so the
                # final inspect/create still has a narrow race.
                manifest = self.inspect(ref, "--raw", allow_missing=True)
                if manifest is not None:
                    if self.children(manifest) != snapshot["children"][image]:
                        raise PublicationError(
                            "Docker immutable tag conflicts with tested source digests"
                        )
                    continue
                refs = [
                    f"{image}@{snapshot['children'][image][arch]}"
                    for arch in ("amd64", "arm64")
                ]
                run_command(
                    ["docker", "buildx", "imagetools", "create", "--tag", ref, *refs]
                )
            self.verify_docker(snapshot["children"], complete=True)
            latest = snapshot["latest"] and self.latest(release)
            release = self.recheck_before_write(snapshot)
            if latest and release["draft"]:
                for image in self.images:
                    refs = [
                        f"{image}@{snapshot['children'][image][arch]}"
                        for arch in ("amd64", "arm64")
                    ]
                    run_command(
                        [
                            "docker",
                            "buildx",
                            "imagetools",
                            "create",
                            "--tag",
                            f"{image}:latest",
                            *refs,
                        ]
                    )
                    if (
                        self.children(self.inspect(f"{image}:latest", "--raw"))
                        != snapshot["children"][image]
                    ):
                        raise PublicationError("Docker latest promotion did not verify")
        else:
            # A human may publish while the initial draft preflight is running.
            # Verification-only mode still requires every immutable tag.
            self.verify_docker(snapshot["children"], complete=True)
        digests = self.manifest_digests(snapshot["children"])
        return {
            "ghcr_digest": digests[self.images[0]],
            "dockerhub_digest": digests[self.images[1]],
        }

    def verify_attestations(self, snapshot, digests):
        targets = [str(self.assets_dir / name) for name in snapshot["assets"]]
        targets += [str(self.dist_dir / name) for name in snapshot["dist"]]
        targets += [
            f"oci://{'docker.io/' if image == 'ledfxorg/ledfx' else ''}{image}@{digest}"
            for image, digest in digests.items()
        ]
        for target in targets:
            run_command(
                [
                    "gh",
                    "attestation",
                    "verify",
                    target,
                    "--repo",
                    self.repo,
                    "--signer-workflow",
                    f"{self.repo}/.github/workflows/ci.yml",
                    "--source-digest",
                    self.sha,
                    "--source-ref",
                    f"refs/tags/{self.tag}",
                    "--deny-self-hosted-runners",
                ]
            )

    def finalize(self):
        snapshot, release = self.load_snapshot()
        self.verify_assets(release, snapshot["assets"], complete=True)
        self.verify_pypi(snapshot["dist"], complete=True)
        self.verify_docker(snapshot["children"], complete=True)
        digests = self.manifest_digests(snapshot["children"])
        self.verify_attestations(snapshot, digests)
        latest = release["draft"] and snapshot["latest"] and self.latest(release)
        release = self.recheck_before_write(snapshot)
        if release["draft"]:
            # Address the verified immutable ID, so replacing the tag's release
            # cannot redirect this write to an unverified replacement release.
            run_command(
                [
                    "gh",
                    "api",
                    f"repos/{self.repo}/releases/{snapshot['release_id']}",
                    "--method",
                    "PATCH",
                    "-F",
                    "draft=false",
                    "-f",
                    f"make_latest={str(latest).lower()}",
                ]
            )
        public = self.release()
        if (
            public["draft"]
            or public["id"] != snapshot["release_id"]
            or public["body"] != release["body"]
            or public["prerelease"] != snapshot["prerelease"]
        ):
            raise PublicationError("Public GitHub release metadata did not verify")
        self.verify_assets(public, snapshot["assets"], complete=True)
        return {}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "promote", "finalize"))
    for flag in ("assets", "dist", "docker-digests", "snapshot"):
        parser.add_argument(f"--{flag}", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        publisher = Publisher(
            args.assets, args.dist, args.docker_digests, args.snapshot
        )
        outputs = getattr(publisher, args.phase)()
        if outputs:
            output = os.environ.get("GITHUB_OUTPUT")
            if not output:
                raise PublicationError("GITHUB_OUTPUT is required")
            with Path(output).open("a") as file:
                file.writelines(
                    f"{key}={str(value).lower()}\n" for key, value in outputs.items()
                )
        return 0
    except PublicationError as error:
        print(f"Release publication failed: {error}", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        print(
            "Release publication failed: invalid metadata or local input",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
