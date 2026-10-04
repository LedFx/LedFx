"""Release notification recovery contracts; every service is simulated locally."""

import base64
import copy
import importlib.util
import io
import json
import os
import sys
from email.message import Message
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request
from urllib.response import addinfourl

import pytest

SCRIPTS = Path(__file__).parents[1] / ".github" / "ci_scripts"
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location(
    "announce_release", SCRIPTS / "announce_release.py"
)
assert _spec and _spec.loader
announce_release = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(announce_release)

REPO = "LedFx/LedFx"
RELEASE = {
    "id": 1234,
    "draft": False,
    "body": "### Features\n* Added device support.\n### Bug Fixes\n* Fixed crashes.",
    "tag_name": "v2.2.0",
    "html_url": "https://github.com/LedFx/LedFx/releases/tag/v2.2.0",
    "assets": [
        {"name": f"LedFx-2.2.0-{suffix}"}
        for suffix in (
            "win-x64.zip",
            "win-x64-setup.zip",
            "osx-arm64.tar.gz",
            "osx-intel.tar.gz",
        )
    ],
}
WEBHOOK = "https://discord.com/api/webhooks/123/secret-token?thread_id=456&wait=false"
ENV = {
    "GITHUB_REPOSITORY": REPO,
    "RELEASE_STATE_TOKEN": "state-secret",
    "SHAUNS_OPENROUTER_KEY": "test-api-key",
    "DISCORD_ANNOUNCEMENTS_WEBHOOK": WEBHOOK,
    "DISCORD_RELEASETHREAD_WEBHOOK": WEBHOOK,
    "OPENROUTER_MODEL": "test/model",
}


class TransportResponse(addinfourl):
    """urllib transport response with its HTTP reason phrase."""

    msg: str = "Transport response"


def response(data: object) -> io.BytesIO:
    return io.BytesIO(json.dumps(data).encode())


def http_error(code: int, body: object = None) -> HTTPError:
    return HTTPError(WEBHOOK, code, "secret-token", Message(), response(body or {}))


class Services:
    """Emulate Contents JSON/CAS, plus confirmed/failed Discord responses."""

    def __init__(self) -> None:
        self.state = {}
        self.exists = False
        self.sha: str | None = None
        self.events = []
        self.discord_results = []
        self.summary_result: object = {
            "choices": [{"message": {"content": "- Fixed crashes."}}]
        }
        self.save_failure: int | None = None
        self.saves = 0

    def open(self, request: Request, timeout: float) -> io.BytesIO:
        url = request.full_url
        data = request.data
        assert data is None or isinstance(data, bytes)
        payload = json.loads(data or b"{}")
        if url.startswith("https://api.github.com/"):
            assert request.get_header("Authorization") == "Bearer state-secret"
            if "/git/ref/" in url:
                return response(
                    {
                        "ref": "refs/heads/automation/release-notifications",
                        "object": {"type": "commit", "sha": "a" * 40},
                    }
                )
            assert "/contents/releases/1234.json" in url
            if request.method == "GET":
                self.events.append(("load", copy.deepcopy(self.state)))
                if not self.exists:
                    raise http_error(404)
                return response(
                    {
                        "type": "file",
                        "sha": self.sha,
                        "encoding": "base64",
                        "content": base64.b64encode(
                            json.dumps(self.state).encode()
                        ).decode(),
                    }
                )
            self.saves += 1
            self.events.append(("save", copy.deepcopy(payload)))
            if self.saves == self.save_failure:
                raise http_error(500)
            assert payload.get("sha") == self.sha
            self.state = json.loads(base64.b64decode(payload["content"]))
            self.exists = True
            self.sha = f"{self.saves:040x}"
            return response({"content": {"sha": self.sha}})
        assert request.get_header("Authorization") != "Bearer state-secret"
        if url == announce_release.OPENROUTER_URL:
            assert request.get_header("Authorization") == "Bearer test-api-key"
            self.events.append(("llm", payload))
            if isinstance(self.summary_result, Exception):
                raise self.summary_result
            return response(self.summary_result)
        assert request.get_header("Authorization") is None
        self.events.append(
            (
                "discord",
                {"url": url, "payload": payload, "state": copy.deepcopy(self.state)},
            )
        )
        result = (
            self.discord_results.pop(0)
            if self.discord_results
            else {"id": str(700 + len(self.events)), "channel_id": "987"}
        )
        if isinstance(result, Exception):
            raise result
        return response(result)

    @property
    def posts(self):
        return [event[1] for event in self.events if event[0] == "discord"]


def run_main(
    tmp_path: Path,
    release: object = RELEASE,
    *,
    services: Services | None = None,
    env: dict[str, str] = ENV,
    dry_run: bool = False,
) -> int:
    path = tmp_path / "release.json"
    path.write_text(json.dumps(release), encoding="utf-8")
    argv = ["announce_release.py", str(path)] + (["--dry-run"] if dry_run else [])
    with patch.dict(os.environ, env, clear=True), patch.object(sys, "argv", argv):
        if services is None:
            return announce_release.main()
        with (
            patch("urllib.request.urlopen", services.open),
            patch.object(announce_release, "urlopen", services.open),
        ):
            # Imported helper owns a distinct network boundary.
            module = sys.modules.get("release_state")
            if module:
                with patch.object(module, "urlopen", services.open):
                    return announce_release.main()
            return announce_release.main()


def test_full_thread_precedes_summary_and_every_post_has_durable_pending(
    tmp_path: Path,
) -> None:
    services = Services()
    assert run_main(tmp_path, services=services) == 0
    thread, announcement = services.posts
    assert thread["payload"]["thread_name"] == "LedFx v2.2.0"
    assert (
        thread["payload"]["content"]
        == RELEASE["body"] + "\n\nRelease and downloads: " + RELEASE["html_url"]
    )
    assert parse_qs(urlsplit(thread["url"]).query) == {"wait": ["true"]}
    assert "<#987>" in announcement["payload"]["content"]
    assert RELEASE["html_url"] in announcement["payload"]["content"]
    assert [kind for kind, _ in services.events].index("discord") < [
        kind for kind, _ in services.events
    ].index("llm")
    for post in services.posts:
        assert post["state"]["pending"] is not None
        assert post["payload"]["allowed_mentions"] == {"parse": []}
        assert len(post["payload"]["content"]) <= 2000
        assert parse_qs(urlsplit(post["url"]).query)["wait"] == ["true"]
    assert services.state["pending"] is None
    assert services.state["announcement"]["id"].isdigit()
    assert "secret-token" not in json.dumps(services.state)
    assert "state-secret" not in json.dumps(services.state)


@pytest.mark.parametrize(
    "summary",
    [
        {},
        {"choices": []},
        {"choices": [{"message": {"content": ""}}]},
        {"choices": [{"message": {"content": "Invented plain text"}}]},
        URLError("test-api-key"),
    ],
    ids=["missing", "empty-choices", "empty", "not-bullets", "network"],
)
def test_summary_failure_uses_factual_fallback_after_full_thread(
    tmp_path: Path, summary: object
) -> None:
    services = Services()
    services.summary_result = summary
    assert run_main(tmp_path, services=services) == 0
    assert "v2.2.0" in services.posts[-1]["payload"]["content"]
    assert len(services.posts) == 2


def test_optional_key_skips_llm_and_still_delivers(tmp_path: Path) -> None:
    services = Services()
    assert (
        run_main(
            tmp_path,
            services=services,
            env={
                key: value
                for key, value in ENV.items()
                if key != "SHAUNS_OPENROUTER_KEY"
            },
        )
        == 0
    )
    assert not any(kind == "llm" for kind, _ in services.events)


@pytest.mark.parametrize(
    "change",
    [
        {"draft": True},
        {"id": True},
        {"id": 0},
        {"body": " "},
        {"html_url": "https://github.com/other/repo/releases/tag/v2.2.0"},
        {"tag_name": "../../bad"},
        {"assets": []},
        {"assets": RELEASE["assets"] * 2},
    ],
    ids=[
        "draft",
        "bool-id",
        "zero-id",
        "empty",
        "foreign-url",
        "tag",
        "assets",
        "duplicates",
    ],
)
def test_invalid_release_never_calls_services(
    tmp_path: Path, change: dict[str, object]
) -> None:
    services = Services()
    assert run_main(tmp_path, {**RELEASE, **change}, services=services) == 1
    assert services.events == []


@pytest.mark.parametrize("tag", ["v2.2.0", "v2.2.0rc1", "v2.2.0-beta.2"])
def test_publisher_version_conventions_are_accepted(tmp_path: Path, tag: str) -> None:
    release = copy.deepcopy(RELEASE)
    release["tag_name"] = tag
    release["html_url"] = f"https://github.com/{REPO}/releases/tag/{tag}"
    for asset in release["assets"]:
        asset["name"] = asset["name"].replace("2.2.0", tag[1:])
    assert run_main(tmp_path, release, services=Services()) == 0


@pytest.mark.parametrize(
    "changelog",
    ["* Changes.\n" * 900, "x" * 9000, "✨" * 9000],
    ids=["multiline", "long-line", "unicode"],
)
def test_entire_long_body_is_preserved_in_single_thread(
    tmp_path: Path, changelog: str
) -> None:
    services = Services()
    assert run_main(tmp_path, {**RELEASE, "body": changelog}, services=services) == 0
    posts = services.posts[:-1]
    assert (
        "".join(post["payload"]["content"] for post in posts)
        == changelog + "\n\nRelease and downloads: " + RELEASE["html_url"]
    )
    assert sum("thread_name" in post["payload"] for post in posts) == 1
    assert all(
        parse_qs(urlsplit(post["url"]).query)["thread_id"] == ["987"]
        for post in posts[1:]
    )
    assert len(services.state["message_ids"]) == len(posts)


@pytest.mark.parametrize(
    "failure",
    [
        TimeoutError("secret-token"),
        URLError(WEBHOOK),
        http_error(408),
        http_error(500),
        {},
        {"id": "42"},
        {"id": "invalid", "channel_id": "987"},
    ],
    ids=[
        "timeout",
        "network",
        "408",
        "500",
        "missing-ids",
        "missing-channel",
        "bad-id",
    ],
)
def test_ambiguous_delivery_blocks_retry_without_replay(
    tmp_path: Path, failure: object, capsys: pytest.CaptureFixture[str]
) -> None:
    services = Services()
    services.discord_results = [failure]
    assert run_main(tmp_path, services=services) == 1
    assert services.state["pending"] is not None
    posts = len(services.posts)
    assert run_main(tmp_path, services=services) == 1
    assert len(services.posts) == posts
    error = capsys.readouterr().err
    assert "releases/1234.json" in error
    assert "reconcil" in error.lower()
    assert all(
        secret not in error
        for secret in ["secret-token", "test-api-key", "state-secret", WEBHOOK]
    )


@pytest.mark.parametrize("code", [400, 401, 403, 404, 429])
def test_definite_rejection_clears_pending_and_allows_retry(
    tmp_path: Path, code: int
) -> None:
    services = Services()
    services.discord_results = [http_error(code, {"retry_after": 31})]
    assert run_main(tmp_path, services=services) == 1
    assert services.state["pending"] is None
    assert run_main(tmp_path, services=services) == 0
    assert len(services.posts) == 3


@pytest.mark.parametrize("failure_save", [1, 2])
def test_save_failure_before_post_never_sends(
    tmp_path: Path, failure_save: int
) -> None:
    services = Services()
    services.save_failure = failure_save
    assert run_main(tmp_path, services=services) == 1
    assert not services.posts


def test_lost_confirmation_save_leaves_remote_pending_and_blocks_replay(
    tmp_path: Path,
) -> None:
    services = Services()
    services.save_failure = 3
    assert run_main(tmp_path, services=services) == 1
    assert len(services.posts) == 1
    assert services.state["pending"] is not None
    assert run_main(tmp_path, services=services) == 1
    assert len(services.posts) == 1


def test_confirmed_partial_thread_resumes_without_recreating_thread(
    tmp_path: Path,
) -> None:
    services = Services()
    services.discord_results = [{"id": "71", "channel_id": "987"}, http_error(400)]
    release = {**RELEASE, "body": "x" * 5000}
    assert run_main(tmp_path, release, services=services) == 1
    assert services.state["message_ids"] == ["71"]
    before = len(services.posts)
    assert run_main(tmp_path, release, services=services) == 0
    assert all("thread_name" not in post["payload"] for post in services.posts[before:])
    assert services.posts[before]["payload"]["content"] == "x" * 2000


def test_announcement_only_retry_reuses_saved_summary_and_completed_retry_skips(
    tmp_path: Path,
) -> None:
    services = Services()
    services.discord_results = [{"id": "71", "channel_id": "987"}, http_error(400)]
    assert run_main(tmp_path, services=services) == 1
    content = services.state["announcement"]["content"]
    assert run_main(tmp_path, services=services) == 0
    assert services.posts[-1]["payload"]["content"] == content
    assert sum(kind == "llm" for kind, _ in services.events) == 1
    before = len(services.posts)
    assert run_main(tmp_path, services=services) == 0
    assert len(services.posts) == before


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "tag",
        "release_id",
        "source_sha256",
        "chunk_sha256",
        "message_ids",
        "announcement",
    ],
    ids=["schema", "tag", "id", "source", "chunks", "ids", "announcement"],
)
def test_corrupt_or_mismatched_state_stops_before_discord(
    tmp_path: Path, field: str
) -> None:
    services = Services()
    assert run_main(tmp_path, services=services) == 0
    services.state[field] = "corrupt"
    before = len(services.posts)
    assert run_main(tmp_path, services=services) == 1
    assert len(services.posts) == before


def test_changed_release_body_rejected_before_replay(tmp_path: Path) -> None:
    services = Services()
    assert run_main(tmp_path, services=services) == 0
    before = len(services.posts)
    assert (
        run_main(
            tmp_path, {**RELEASE, "body": RELEASE["body"] + "new"}, services=services
        )
        == 1
    )
    assert len(services.posts) == before


@pytest.mark.parametrize("with_key", [False, True])
def test_dry_run_needs_no_state_or_discord_credentials(
    tmp_path: Path, with_key: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    services = Services()
    env = {"GITHUB_REPOSITORY": REPO}
    if with_key:
        env["SHAUNS_OPENROUTER_KEY"] = "test-api-key"
    assert run_main(tmp_path, services=services, env=env, dry_run=True) == 0
    assert all(kind == "llm" for kind, _ in services.events)
    assert len(services.events) == int(with_key)
    output = capsys.readouterr().out
    assert RELEASE["body"] in output
    assert RELEASE["html_url"] in output


def test_rate_limit_retries_are_bounded_and_confirm_same_post(tmp_path: Path) -> None:
    services = Services()
    services.discord_results = [http_error(429, {"retry_after": 0.5}) for _ in range(3)]
    with patch.object(announce_release.time, "sleep") as sleep:
        assert run_main(tmp_path, services=services) == 1
        assert sleep.call_count == 2
    assert len(services.posts) == 3
    assert services.posts[0] == services.posts[1] == services.posts[2]
    assert services.state["pending"] is None


@pytest.mark.parametrize("operation", ["followup", "announcement"])
def test_missing_message_confirmation_after_first_chunk_blocks_without_replay(
    tmp_path: Path, operation: str
) -> None:
    services = Services()
    services.discord_results = [
        {"id": "71", "channel_id": "987"},
        {"channel_id": "987"},
    ]
    release = {**RELEASE, "body": "x" * 5000} if operation == "followup" else RELEASE
    assert run_main(tmp_path, release, services=services) == 1
    assert services.state["message_ids"] == ["71"]
    assert services.state["pending"]["kind"] == (
        "chunk" if operation == "followup" else "announcement"
    )
    before = len(services.posts)
    assert run_main(tmp_path, release, services=services) == 1
    assert len(services.posts) == before


def test_llm_receives_unmodified_full_body_and_override_after_thread(
    tmp_path: Path,
) -> None:
    services = Services()
    assert run_main(tmp_path, services=services) == 0
    payload = next(data for kind, data in services.events if kind == "llm")
    assert payload["model"] == "test/model"
    assert payload["messages"][1]["content"] == RELEASE["body"]


def test_long_summary_keeps_public_release_and_thread_links() -> None:
    content = announce_release.announcement(
        "v2.2.0", RELEASE["html_url"], "- Change. " * 1000, "987"
    )
    assert len(content) <= 2000
    assert "…" in content
    assert "<#987>" in content
    assert content.endswith(RELEASE["html_url"])


@pytest.mark.parametrize(
    "failure",
    [b"not-json", b"[]", b"null", b"\xff"],
    ids=["malformed", "array", "null", "utf8"],
)
def test_malformed_response_remains_ambiguous_and_redacted(failure: bytes) -> None:
    with patch.object(announce_release, "urlopen", return_value=io.BytesIO(failure)):
        with pytest.raises(RuntimeError) as caught:
            announce_release.post_json(WEBHOOK, {"content": "notes"}, {}, "Discord")
        assert getattr(caught.value, "rejected", None) is False
        assert "secret-token" not in str(caught.value)


def test_incomplete_http_read_is_redacted_ambiguous_delivery() -> None:
    from http.client import IncompleteRead

    with patch.object(
        announce_release, "urlopen", side_effect=IncompleteRead(b"secret-token")
    ):
        with pytest.raises(RuntimeError) as caught:
            announce_release.post_json(WEBHOOK, {"content": "notes"}, {}, "Discord")
        assert getattr(caught.value, "rejected", None) is False
        assert "secret-token" not in str(caught.value)


@pytest.mark.parametrize(
    "delay", [31, -1, "nan", "inf"], ids=["too-long", "negative", "nan", "inf"]
)
def test_rate_limit_delay_outside_bound_is_not_slept_or_retried(delay: object) -> None:
    with (
        patch.object(
            announce_release,
            "urlopen",
            side_effect=http_error(429, {"retry_after": delay}),
        ) as network,
        patch.object(announce_release.time, "sleep") as sleep,
    ):
        with pytest.raises(RuntimeError) as caught:
            announce_release.post_json(WEBHOOK, {"content": "notes"}, {}, "Discord")
        assert getattr(caught.value, "rejected", None) is True
        assert network.call_count == 1
        sleep.assert_not_called()


@pytest.mark.parametrize(
    "corrupt",
    [
        {"kind": "chunk", "index": 9, "sha256": "bad"},
        {"kind": "announcement", "sha256": "bad"},
        "bad",
    ],
)
def test_corrupt_pending_record_cannot_be_manually_replayed(
    tmp_path: Path, corrupt: object
) -> None:
    services = Services()
    services.discord_results = [TimeoutError()]
    assert run_main(tmp_path, services=services) == 1
    services.state["pending"] = corrupt
    before = len(services.posts)
    assert run_main(tmp_path, services=services) == 1
    assert len(services.posts) == before


def test_incomplete_rate_limit_body_uses_bounded_fallback_delay() -> None:
    from http.client import IncompleteRead

    error = http_error(429)
    with (
        patch.object(error, "read", side_effect=IncompleteRead(b"secret-token")),
        patch.object(
            announce_release, "urlopen", side_effect=[error, response({"id": "7"})]
        ) as network,
        patch.object(announce_release.time, "sleep") as sleep,
    ):
        assert (
            announce_release.post_json(WEBHOOK, {"content": "notes"}, {}, "Discord")[
                "id"
            ]
            == "7"
        )
        assert network.call_count == 2
        sleep.assert_called_once_with(1.0)


def test_fallback_does_not_promise_upgrade_notes(tmp_path: Path) -> None:
    services = Services()
    env = {key: value for key, value in ENV.items() if key != "SHAUNS_OPENROUTER_KEY"}
    assert run_main(tmp_path, services=services, env=env) == 0
    assert "upgrade notes" not in services.posts[-1]["payload"]["content"]


def test_invalid_unicode_summary_uses_fallback_instead_of_stopping_delivery(
    tmp_path: Path,
) -> None:
    services = Services()
    services.summary_result = {
        "choices": [{"message": {"content": "- Broken \ud800 text."}}]
    }
    assert run_main(tmp_path, services=services) == 0
    assert "release details" in services.posts[-1]["payload"]["content"]


def test_overflowing_rate_limit_delay_uses_bounded_fallback_and_clears_rejection(
    tmp_path: Path,
) -> None:
    services = Services()
    services.discord_results = [
        http_error(429, {"retry_after": 10**400}) for _ in range(3)
    ]
    with patch.object(announce_release.time, "sleep") as sleep:
        assert run_main(tmp_path, services=services) == 1
        assert sleep.call_args_list == [((1.0,),), ((1.0,),)]
    assert len(services.posts) == 3
    assert services.state["pending"] is None
    assert run_main(tmp_path, services=services) == 0


@pytest.mark.parametrize("code", [301, 302])
def test_post_redirect_never_forwards_api_key_or_sends_second_request(
    code: int,
) -> None:
    from urllib.request import build_opener

    state_module = sys.modules["release_state"]
    opener = getattr(state_module, "_OPENER", build_opener())
    headers = Message()
    headers["Location"] = "https://other-host.invalid/capture"
    redirect = TransportResponse(
        io.BytesIO(b"secret-response"), headers, announce_release.OPENROUTER_URL, code
    )
    redirect.msg = "Redirect"
    success = TransportResponse(
        response({"id": "7"}), Message(), "https://other-host.invalid/capture", 200
    )
    success.msg = "OK"
    with (
        patch("urllib.request._opener", opener),
        patch.object(opener, "_open", side_effect=[redirect, success]) as transport,
    ):
        with pytest.raises(RuntimeError) as caught:
            announce_release.post_json(
                announce_release.OPENROUTER_URL,
                {"content": "notes"},
                {"Authorization": "Bearer test-api-key"},
                "OpenRouter",
            )
        assert transport.call_count == 1
        assert transport.call_args.args[0].full_url == announce_release.OPENROUTER_URL
        assert "test-api-key" not in str(caught.value)
        assert "secret-response" not in str(caught.value)


def test_leading_blank_line_does_not_create_blank_first_message() -> None:
    notes = "\n" + "x" * 2001
    chunks = announce_release.split_changelog(notes)
    assert chunks[0] == notes[:2000]
    assert "".join(chunks) == notes
    assert all(chunk.strip() and len(chunk) <= 2000 for chunk in chunks)


@pytest.mark.parametrize(
    "notes",
    [
        " " * 5000 + "Release details.",
        "\n" * 5000 + "Release details.",
        "Release details.\n" + " \t\n" * 2000,
    ],
    ids=["leading-spaces", "leading-newlines", "trailing-mixed"],
)
def test_whitespace_only_messages_are_framed_without_losing_notes(
    tmp_path: Path, notes: str
) -> None:
    services = Services()
    assert run_main(tmp_path, {**RELEASE, "body": notes}, services=services) == 0
    thread_messages = [post["payload"]["content"] for post in services.posts[:-1]]
    reconstructed = "".join(
        content[4:-4]
        if content.startswith("```\n") and content.endswith("\n```")
        else content
        for content in thread_messages
    )
    assert reconstructed == notes + "\n\nRelease and downloads: " + RELEASE["html_url"]
    assert any(content.startswith("```\n") for content in thread_messages)
    assert all(content.strip() and len(content) <= 2000 for content in thread_messages)
    assert services.state["chunk_sha256"] == [
        announce_release.digest(content) for content in thread_messages
    ]


def test_whitespace_only_followup_resumes_with_same_framed_content(
    tmp_path: Path,
) -> None:
    services = Services()
    release = {**RELEASE, "body": " " * 5000 + "Release details."}
    services.discord_results = [{"id": "71", "channel_id": "987"}, http_error(400)]
    assert run_main(tmp_path, release, services=services) == 1
    rejected_content = services.posts[-1]["payload"]["content"]
    assert rejected_content.startswith("```\n") and rejected_content.endswith("\n```")
    before = len(services.posts)
    assert run_main(tmp_path, release, services=services) == 0
    assert services.posts[before]["payload"]["content"] == rejected_content
    assert "thread_name" not in services.posts[before]["payload"]


def test_resume_rejects_old_unframed_chunk_hashes_before_discord(
    tmp_path: Path,
) -> None:
    services = Services()
    release = {**RELEASE, "body": " " * 5000 + "Release details."}
    services.discord_results = [{"id": "71", "channel_id": "987"}, http_error(400)]
    assert run_main(tmp_path, release, services=services) == 1
    services.state["chunk_sha256"][0] = announce_release.digest(" " * 2000)
    before = len(services.posts)
    assert run_main(tmp_path, release, services=services) == 1
    assert len(services.posts) == before
