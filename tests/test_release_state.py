"""Stdlib GitHub state API contracts, including explicit absence and CAS."""

import base64
import importlib.util
import io
import json
from email.message import Message
from pathlib import Path
from types import ModuleType
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.response import addinfourl

import pytest

SCRIPT = Path(__file__).parents[1] / ".github" / "ci_scripts" / "release_state.py"
SHA = "a" * 40
BRANCH = "automation/release-notifications"
REF = {"ref": f"refs/heads/{BRANCH}", "object": {"type": "commit", "sha": SHA}}


class TransportResponse(addinfourl):
    """urllib transport response with its HTTP reason phrase."""

    msg: str = "Transport response"


def module() -> ModuleType:
    assert SCRIPT.exists(), "Durable GitHub state store is not implemented"
    spec = importlib.util.spec_from_file_location("tested_release_state", SCRIPT)
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def reply(data: object) -> io.BytesIO:
    return io.BytesIO(json.dumps(data).encode())


def error(code: int) -> HTTPError:
    return HTTPError(
        "https://api.github.com/secret", code, "state-secret", Message(), None
    )


def file_response(state: object):
    return {
        "type": "file",
        "sha": SHA,
        "encoding": "base64",
        "content": base64.b64encode(json.dumps(state).encode()).decode(),
    }


def test_load_and_save_use_base64_json_and_last_sha_for_cas() -> None:
    state_module = module()
    initial = {"schema_version": 1}
    with patch.object(
        state_module,
        "urlopen",
        side_effect=[
            reply(REF),
            reply(file_response(initial)),
            reply({"content": {"sha": "b" * 40}}),
            reply({"content": {"sha": "c" * 40}}),
        ],
    ) as network:
        store = state_module.ReleaseStateStore("LedFx/LedFx", 1234, "state-secret")
        assert store.load() == initial
        store.save({"schema_version": 1, "pending": {"kind": "chunk"}})
        store.save(initial)
        calls = [call.args[0] for call in network.call_args_list]
        assert (
            calls[0].full_url
            == f"https://api.github.com/repos/LedFx/LedFx/git/ref/heads/{BRANCH}"
        )
        assert (
            calls[1].full_url
            == "https://api.github.com/repos/LedFx/LedFx/contents/releases/1234.json?ref=automation%2Frelease-notifications"
        )
        assert calls[2].method == "PUT"
        put = json.loads(calls[2].data)
        assert put["sha"] == SHA
        assert put["branch"] == BRANCH
        assert json.loads(base64.b64decode(put["content"]))["pending"] == {
            "kind": "chunk"
        }
        assert json.loads(calls[3].data)["sha"] == "b" * 40
        assert all(
            call.get_header("Authorization") == "Bearer state-secret" for call in calls
        )


def test_first_save_has_no_blob_sha() -> None:
    state_module = module()
    with patch.object(
        state_module,
        "urlopen",
        side_effect=[reply(REF), error(404), reply({"content": {"sha": SHA}})],
    ) as network:
        store = state_module.ReleaseStateStore("LedFx/LedFx", 1234, "state-secret")
        assert store.load() is None
        store.save({"schema_version": 1})
        assert "sha" not in json.loads(network.call_args.args[0].data)


@pytest.mark.parametrize(
    "failure",
    [
        error(401),
        error(403),
        error(500),
        URLError("state-secret"),
        TimeoutError("state-secret"),
    ],
    ids=["401", "403", "500", "network", "timeout"],
)
def test_auth_network_and_server_failures_are_not_branch_absence(
    failure: object,
) -> None:
    state_module = module()
    with patch.object(state_module, "urlopen", side_effect=failure) as network:
        with pytest.raises(RuntimeError) as caught:
            state_module.ReleaseStateStore("LedFx/LedFx", 1234, "state-secret").load()
        assert network.call_count == 1
        assert "state-secret" not in str(caught.value)


def test_missing_branch_initializes_from_repository_default_branch_head() -> None:
    state_module = module()
    default_ref = {"ref": "refs/heads/main", "object": {"type": "commit", "sha": SHA}}
    with patch.object(
        state_module,
        "urlopen",
        side_effect=[
            error(404),
            reply({"default_branch": "main"}),
            reply(default_ref),
            reply(REF),
            error(404),
        ],
    ) as network:
        store = state_module.ReleaseStateStore("LedFx/LedFx", 1234, "state-secret")
        assert store.load() is None
        requests = [call.args[0] for call in network.call_args_list]
        assert requests[1].full_url.endswith("/repos/LedFx/LedFx")
        assert requests[2].full_url.endswith("/git/ref/heads/main")
        assert requests[3].method == "POST"
        assert json.loads(requests[3].data) == {
            "ref": f"refs/heads/{BRANCH}",
            "sha": SHA,
        }


@pytest.mark.parametrize("code", [409, 422])
def test_explicit_branch_create_rejection_can_accept_confirmed_racing_creation(
    code: int,
) -> None:
    state_module = module()
    with patch.object(
        state_module,
        "urlopen",
        side_effect=[
            error(404),
            reply({"default_branch": "main"}),
            reply({"ref": "refs/heads/main", "object": {"type": "commit", "sha": SHA}}),
            error(code),
            reply(REF),
            error(404),
        ],
    ) as network:
        assert (
            state_module.ReleaseStateStore("LedFx/LedFx", 1234, "state-secret").load()
            is None
        )
        assert network.call_count == 6


@pytest.mark.parametrize(
    "failure",
    [error(500), URLError("state-secret"), TimeoutError("state-secret")],
    ids=["500", "network", "timeout"],
)
def test_uncertain_branch_create_never_retries_or_accepts_assumed_race(
    failure: object,
) -> None:
    state_module = module()
    with patch.object(
        state_module,
        "urlopen",
        side_effect=[
            error(404),
            reply({"default_branch": "main"}),
            reply({"ref": "refs/heads/main", "object": {"type": "commit", "sha": SHA}}),
            failure,
        ],
    ) as network:
        with pytest.raises(RuntimeError):
            state_module.ReleaseStateStore("LedFx/LedFx", 1234, "state-secret").load()
        assert network.call_count == 4


def test_branch_create_rejection_with_missing_branch_is_fatal() -> None:
    state_module = module()
    with (
        patch.object(
            state_module,
            "urlopen",
            side_effect=[
                error(404),
                reply({"default_branch": "main"}),
                reply(
                    {"ref": "refs/heads/main", "object": {"type": "commit", "sha": SHA}}
                ),
                error(422),
                error(404),
            ],
        ),
        pytest.raises(RuntimeError),
    ):
        state_module.ReleaseStateStore("LedFx/LedFx", 1234, "state-secret").load()


@pytest.mark.parametrize(
    "failure",
    [error(409), error(422), error(500), TimeoutError("state-secret"), reply({})],
    ids=["conflict", "rejected", "500", "timeout", "missing-sha"],
)
def test_state_write_failure_is_not_retried(failure: object) -> None:
    state_module = module()
    with patch.object(
        state_module,
        "urlopen",
        side_effect=[reply(REF), reply(file_response({})), failure],
    ) as network:
        store = state_module.ReleaseStateStore("LedFx/LedFx", 1234, "state-secret")
        store.load()
        with pytest.raises(RuntimeError):
            store.save({"pending": {"kind": "chunk"}})
        assert network.call_count == 3


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {**file_response({}), "type": "dir"},
        {**file_response({}), "sha": "bad"},
        {**file_response({}), "encoding": "raw"},
        {**file_response({}), "content": "%%%"},
        {**file_response({}), "content": base64.b64encode(b"not json").decode()},
        file_response([]),
    ],
    ids=["empty", "directory", "bad-sha", "encoding", "base64", "json", "array"],
)
def test_corrupt_contents_never_turn_into_absent_state(bad: object) -> None:
    state_module = module()
    with patch.object(
        state_module, "urlopen", side_effect=[reply(REF), reply(bad)]
    ) as network:
        with pytest.raises(RuntimeError):
            state_module.ReleaseStateStore("LedFx/LedFx", 1234, "state-secret").load()
        assert network.call_count == 2


@pytest.mark.parametrize(
    "repo, release_id, token",
    [
        ("../evil", 1, "key"),
        ("a/b/c", 1, "key"),
        ("a/b", True, "key"),
        ("a/b", -1, "key"),
        ("a/b", "../evil", "key"),
        ("a/b", 1, ""),
    ],
)
def test_invalid_identity_or_missing_explicit_token_never_requests(
    repo: str, release_id: object, token: str
) -> None:
    state_module = module()
    with patch.object(state_module, "urlopen") as network:
        with pytest.raises(RuntimeError):
            state_module.ReleaseStateStore(repo, release_id, token)
        network.assert_not_called()


@pytest.mark.parametrize("code", [401, 403, 500])
def test_contents_auth_or_server_failure_does_not_create_new_state(code: int) -> None:
    state_module = module()
    with patch.object(
        state_module, "urlopen", side_effect=[reply(REF), error(code)]
    ) as network:
        with pytest.raises(RuntimeError):
            state_module.ReleaseStateStore("LedFx/LedFx", 1234, "state-secret").load()
        assert network.call_count == 2


@pytest.mark.parametrize(
    "ref",
    [
        {},
        {**REF, "ref": "refs/heads/other"},
        {**REF, "object": {"type": "tag", "sha": SHA}},
        {**REF, "object": {"type": "commit", "sha": "bad"}},
    ],
    ids=["missing", "foreign", "tag", "sha"],
)
def test_invalid_branch_confirmation_stops_without_state_writes(ref: object) -> None:
    state_module = module()
    with patch.object(state_module, "urlopen", return_value=reply(ref)) as network:
        with pytest.raises(RuntimeError):
            state_module.ReleaseStateStore("LedFx/LedFx", 1234, "state-secret").load()
        assert network.call_count == 1


def test_incomplete_github_response_is_redacted_and_never_retried() -> None:
    from http.client import IncompleteRead

    state_module = module()
    with patch.object(
        state_module, "urlopen", side_effect=IncompleteRead(b"state-secret")
    ) as network:
        with pytest.raises(RuntimeError) as caught:
            state_module.ReleaseStateStore("LedFx/LedFx", 1234, "state-secret").load()
        assert network.call_count == 1
        assert "state-secret" not in str(caught.value)


@pytest.mark.parametrize("code", [301, 302])
def test_github_redirect_never_requests_second_origin_or_forwards_token(
    code: int,
) -> None:
    from urllib.request import build_opener

    state_module = module()
    opener = getattr(state_module, "_OPENER", build_opener())
    headers = Message()
    headers["Location"] = "https://other-host.invalid/capture"
    initial_url = f"https://api.github.com/repos/LedFx/LedFx/git/ref/heads/{BRANCH}"
    redirect = TransportResponse(
        io.BytesIO(b"secret-response"), headers, initial_url, code
    )
    redirect.msg = "Redirect"
    success = TransportResponse(
        reply(REF), Message(), "https://other-host.invalid/capture", 403
    )
    success.msg = "OK"
    with (
        patch("urllib.request._opener", opener),
        patch.object(opener, "_open", side_effect=[redirect, success]) as transport,
    ):
        with pytest.raises(RuntimeError) as caught:
            state_module.ReleaseStateStore("LedFx/LedFx", 1234, "state-secret").load()
        assert transport.call_count == 1
        request = transport.call_args.args[0]
        assert request.full_url == initial_url
        assert request.get_header("Authorization") == "Bearer state-secret"
        assert "state-secret" not in str(caught.value)
        assert "secret-response" not in str(caught.value)
