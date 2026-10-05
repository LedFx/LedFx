"""Credential-isolated stdlib GitHub Contents store for release notifications.

The branch is initialized only after an explicit 404. Contents writes use the
last confirmed blob SHA and are never retried automatically, including conflicts
and uncertain responses. The caller owns the notification state's schema.
"""

import base64
import binascii
import json
import re
import sys
from collections.abc import Callable, Mapping
from http.client import HTTPException, HTTPMessage
from typing import IO, ParamSpec, TypeVar
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

if sys.version_info >= (3, 12):
    from typing import override
else:
    _Parameters = ParamSpec("_Parameters")
    _Return = TypeVar("_Return")

    def override(
        method: Callable[_Parameters, _Return],
    ) -> Callable[_Parameters, _Return]:
        """Preserve method typing on Python 3.11 without runtime dependencies."""
        return method


class _RejectRedirects(HTTPRedirectHandler):
    @override
    def redirect_request(
        self,
        req: Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> None:
        # Redirects must never forward secrets or silently change a POST to GET.
        # urllib turns this refusal into HTTPError, handled by each service.
        return None


_OPENER = build_opener(_RejectRedirects())
urlopen = _OPENER.open

BRANCH = "automation/release-notifications"
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
BLOB_SHA = re.compile(r"[0-9a-f]{40}\Z")


class StateError(RuntimeError):
    """A credential-free GitHub error, with explicit HTTP status if available."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def valid_repository(repository: object) -> bool:
    return (
        isinstance(repository, str)
        and bool(REPOSITORY.fullmatch(repository))
        and all(part not in (".", "..") for part in repository.split("/"))
    )


def valid_release_id(release_id: object) -> bool:
    return type(release_id) is int and release_id > 0


class ReleaseStateStore:
    def __init__(self, repository: str, release_id: int, token: str):
        if not valid_repository(repository) or not valid_release_id(release_id):
            raise StateError("Invalid release state repository or ID")
        if not token.strip():
            raise StateError("RELEASE_STATE_TOKEN must be configured")
        self.path = f"releases/{release_id}.json"
        self._base = f"https://api.github.com/repos/{repository}"
        self._token = token
        self._sha: str | None = None
        self._loaded = False

    def _request(
        self,
        endpoint: str = "",
        method: str = "GET",
        payload: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        request = Request(
            self._base + endpoint,
            data=json.dumps(payload).encode() if payload is not None else None,
            method=method,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
                "User-Agent": "LedFx-release-notifications",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                result = json.load(response)
            if not isinstance(result, dict):
                raise TypeError("Expected object")
            return result
        except HTTPError as error:
            raise StateError(
                f"GitHub release state returned HTTP {error.code}", error.code
            ) from None
        except (URLError, TimeoutError, OSError, HTTPException):
            raise StateError(
                "GitHub release state request failed or timed out"
            ) from None
        except (ValueError, TypeError, UnicodeError):
            raise StateError("GitHub release state returned invalid JSON") from None

    @staticmethod
    def _ref_sha(ref: dict[str, object], branch: str) -> str:
        obj = ref.get("object")
        if (
            ref.get("ref") != f"refs/heads/{branch}"
            or not isinstance(obj, dict)
            or obj.get("type") != "commit"
            or not isinstance(obj.get("sha"), str)
            or not BLOB_SHA.fullmatch(obj["sha"])
        ):
            raise StateError("GitHub release state branch metadata is invalid")
        return obj["sha"]

    def _ensure_branch(self) -> None:
        endpoint = f"/git/ref/heads/{BRANCH}"
        try:
            self._ref_sha(self._request(endpoint), BRANCH)
            return
        except StateError as error:
            if error.status != 404:
                raise
        branch = self._request().get("default_branch")
        if not isinstance(branch, str) or not branch or len(branch) > 255:
            raise StateError("GitHub repository default branch is invalid")
        sha = self._ref_sha(
            self._request(f"/git/ref/heads/{quote(branch, safe='')}"), branch
        )
        try:
            ref = self._request(
                "/git/refs", "POST", {"ref": f"refs/heads/{BRANCH}", "sha": sha}
            )
            self._ref_sha(ref, BRANCH)
        except StateError as error:
            # Only a definite create rejection may indicate another initializer
            # won the race. Auth/server/network errors remain fatal.
            if error.status not in (409, 422):
                raise
            self._ref_sha(self._request(endpoint), BRANCH)

    def load(self) -> dict[str, object] | None:
        self._loaded = False
        self._ensure_branch()
        endpoint = f"/contents/{self.path}?{urlencode({'ref': BRANCH})}"
        try:
            result = self._request(endpoint)
        except StateError as error:
            if error.status != 404:
                raise
            self._sha = None
            self._loaded = True
            return None
        try:
            sha = result["sha"]
            if (
                result.get("type") != "file"
                or result.get("encoding") != "base64"
                or not isinstance(sha, str)
                or not BLOB_SHA.fullmatch(sha)
                or not isinstance(result.get("content"), str)
            ):
                raise ValueError("Invalid Contents response")
            data = base64.b64decode("".join(result["content"].split()), validate=True)
            state = json.loads(data)
            if not isinstance(state, dict):
                raise TypeError("Invalid state object")
        except (KeyError, ValueError, TypeError, UnicodeError, binascii.Error):
            raise StateError(
                "GitHub release state file is corrupt or invalid"
            ) from None
        self._sha = sha
        self._loaded = True
        return state

    def save(self, state: Mapping[str, object]) -> None:
        if not self._loaded:
            raise StateError("Load release state before saving")
        payload = {
            "message": "Record release notification progress",
            "branch": BRANCH,
            "content": base64.b64encode(
                json.dumps(state, sort_keys=True, ensure_ascii=False).encode()
            ).decode(),
        }
        if self._sha is not None:
            payload["sha"] = self._sha
        # Disable further writes on this instance if the result is uncertain.
        self._loaded = False
        result = self._request(f"/contents/{self.path}", "PUT", payload)
        content = result.get("content")
        if (
            not isinstance(content, dict)
            or not isinstance(content.get("sha"), str)
            or not BLOB_SHA.fullmatch(content["sha"])
        ):
            raise StateError("GitHub release state save confirmation is invalid")
        self._sha = content["sha"]
        self._loaded = True
