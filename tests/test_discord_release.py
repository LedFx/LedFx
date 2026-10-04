"""Release announcement contracts; no live OpenRouter or Discord requests."""

import importlib.util
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from email.message import Message
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import pytest

_path = Path(__file__).parents[1] / ".github" / "ci_scripts" / "announce_release.py"
_spec = importlib.util.spec_from_file_location("announce_release", _path)
assert _spec and _spec.loader
announce_release = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(announce_release)

RELEASE = {
    "isDraft": False,
    "body": "### Features\n* Added device support.\n### Bug Fixes\n* Fixed crashes.",
    "tagName": "v2.2.0",
    "url": "https://github.com/LedFx/LedFx/releases/tag/v2.2.0",
}
WEBHOOK = "https://discord.com/api/webhooks/123/secret-token?thread_id=456&wait=false"
ENV = {
    "SHAUNS_OPENROUTER_KEY": "test-api-key",
    "DISCORD_ANNOUNCEMENTS_WEBHOOK": WEBHOOK,
    "DISCORD_RELEASETHREAD_WEBHOOK": WEBHOOK,
    "OPENROUTER_MODEL": "test/model",
}


def run_main(release: object, dry_run: bool = False) -> int:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "release.json"
        path.write_text(json.dumps(release), encoding="utf-8")
        args = ["announce_release.py", str(path)]
        if dry_run:
            args.append("--dry-run")
        with patch.object(sys, "argv", args):
            return announce_release.main()


def test_published_release_uses_its_changelog_and_confirms_discord_delivery():
    summary = "- Added device support.\n- Fixed crashes."
    with (
        patch.dict(os.environ, ENV, clear=True),
        patch.object(announce_release, "urlopen") as urlopen,
    ):
        urlopen.return_value.__enter__.side_effect = [
            io.BytesIO(
                json.dumps({"choices": [{"message": {"content": summary}}]}).encode()
            ),
            io.BytesIO(b'{"id": "789"}'),
            io.BytesIO(b'{"id": "790", "channel_id": "987"}'),
        ]
        assert run_main(RELEASE) == 0
        assert urlopen.call_count == 3
        llm_request = urlopen.call_args_list[0].args[0]
        assert llm_request.full_url == announce_release.OPENROUTER_URL
        assert llm_request.get_header("Authorization") == "Bearer test-api-key"
        llm_payload = json.loads(llm_request.data)
        assert llm_payload["model"] == "test/model"
        assert llm_payload["messages"][1]["content"] == RELEASE["body"]
        discord_request = urlopen.call_args_list[1].args[0]
        assert parse_qs(urlsplit(discord_request.full_url).query) == {
            "thread_id": ["456"],
            "wait": ["true"],
        }
        assert discord_request.get_header("Authorization") is None
        payload = json.loads(discord_request.data)
        assert payload["allowed_mentions"] == {"parse": []}
        assert summary in payload["content"]
        assert RELEASE["tagName"] in payload["content"]
        assert payload["content"].endswith(RELEASE["url"])
        thread_request = urlopen.call_args_list[2].args[0]
        assert parse_qs(urlsplit(thread_request.full_url).query) == {"wait": ["true"]}
        thread_payload = json.loads(thread_request.data)
        assert thread_payload["thread_name"] == "LedFx v2.2.0"
        assert RELEASE["body"] in thread_payload["content"]
        assert thread_payload["allowed_mentions"] == {"parse": []}


def test_long_summary_keeps_release_link_inside_discord_limit():
    content = announce_release.announcement(
        RELEASE["tagName"], RELEASE["url"], "- Change. " * 1000
    )
    assert len(content) <= 2000
    assert "…" in content
    assert content.endswith(RELEASE["url"])


@pytest.mark.parametrize(
    "release",
    [{**RELEASE, "isDraft": True}, {**RELEASE, "body": ""}, {}, None],
)
def test_invalid_release_never_calls_external_services(release: object):
    with (
        patch.dict(os.environ, ENV, clear=True),
        patch.object(announce_release, "urlopen") as urlopen,
    ):
        assert run_main(release) == 1
        urlopen.assert_not_called()


@pytest.mark.parametrize(
    "response", [{}, {"choices": []}, {"choices": [{"message": {"content": " "}}]}]
)
def test_invalid_llm_response_never_posts_to_discord(response: object):
    with (
        patch.dict(os.environ, ENV, clear=True),
        patch.object(announce_release, "urlopen") as urlopen,
    ):
        urlopen.return_value.__enter__.return_value = io.BytesIO(
            json.dumps(response).encode()
        )
        assert run_main(RELEASE) == 1
        assert urlopen.call_count == 1


@pytest.mark.parametrize(
    "error",
    [
        HTTPError(WEBHOOK, 400, "secret-token", Message(), None),
        URLError(WEBHOOK),
        TimeoutError(WEBHOOK),
    ],
)
def test_discord_failure_exits_nonzero_without_logging_secrets(error: Exception):
    stderr = io.StringIO()
    with (
        patch.dict(os.environ, ENV, clear=True),
        patch.object(announce_release, "urlopen") as urlopen,
        redirect_stderr(stderr),
    ):
        urlopen.return_value.__enter__.return_value = io.BytesIO(
            b'{"choices": [{"message": {"content": "- Fixed crashes."}}]}'
        )
        urlopen.side_effect = [urlopen.return_value, error]
        assert run_main(RELEASE) == 1
        assert "Discord" in stderr.getvalue()
        assert "secret-token" not in stderr.getvalue()
        assert "test-api-key" not in stderr.getvalue()


def test_dry_run_does_not_need_webhook_or_post_to_discord():
    stdout = io.StringIO()
    with (
        patch.dict(os.environ, {"SHAUNS_OPENROUTER_KEY": "test-api-key"}, clear=True),
        patch.object(announce_release, "urlopen") as urlopen,
        redirect_stdout(stdout),
    ):
        urlopen.return_value.__enter__.return_value = io.BytesIO(
            b'{"choices": [{"message": {"content": "- Fixed crashes."}}]}'
        )
        assert run_main(RELEASE, dry_run=True) == 0
        assert urlopen.call_count == 1
        assert json.loads(urlopen.call_args.args[0].data)["model"] == "openrouter/auto"
        assert RELEASE["url"] in stdout.getvalue()


def test_missing_secrets_fail_before_external_requests():
    with (
        patch.dict(os.environ, {}, clear=True),
        patch.object(announce_release, "urlopen") as urlopen,
    ):
        assert run_main(RELEASE) == 1
        urlopen.assert_not_called()


@pytest.mark.parametrize("changelog", ["* Changes.\n" * 900, "x" * 9000, "✨" * 9000])
def test_full_changelog_is_preserved_in_one_named_thread(changelog: str):
    with patch.object(announce_release, "urlopen") as urlopen:
        # Each request gets a fresh stream, including the newly created thread ID.
        urlopen.return_value.__enter__.side_effect = lambda: io.BytesIO(
            b'{"id": "790", "channel_id": "987"}'
        )
        announce_release.send_changelog(
            WEBHOOK, RELEASE["tagName"], changelog, RELEASE["url"]
        )
        payloads = [json.loads(call.args[0].data) for call in urlopen.call_args_list]
        assert payloads[0]["thread_name"] == "LedFx v2.2.0"
        assert len(payloads) > 1
        assert "".join(payload["content"] for payload in payloads) == (
            f"{changelog}\n\nRelease and downloads: {RELEASE['url']}"
        )
        for call, payload in zip(urlopen.call_args_list, payloads):
            assert len(payload["content"]) <= 2000
            assert payload["allowed_mentions"] == {"parse": []}
            query = parse_qs(urlsplit(call.args[0].full_url).query)
            assert query["wait"] == ["true"]
            if "thread_name" not in payload:
                assert query["thread_id"] == ["987"]


def test_missing_thread_id_does_not_send_followups_to_the_parent_channel():
    with patch.object(announce_release, "post_json", return_value={}) as post:
        with pytest.raises(RuntimeError, match="no release thread ID"):
            announce_release.send_changelog(
                WEBHOOK, "v2.2.0", "x" * 9000, RELEASE["url"]
            )
        assert post.call_count == 1


def test_rate_limited_discord_post_waits_then_retries_the_same_message():
    error = HTTPError(
        WEBHOOK, 429, "rate limited", Message(), io.BytesIO(b'{"retry_after": 0.5}')
    )
    with (
        patch.object(announce_release, "urlopen") as urlopen,
        patch.object(announce_release.time, "sleep") as sleep,
    ):
        urlopen.return_value.__enter__.return_value = io.BytesIO(b'{"id": "789"}')
        urlopen.side_effect = [error, urlopen.return_value]
        announce_release.send_announcement(WEBHOOK, "Release announcement")
        sleep.assert_called_once_with(0.5)
        assert urlopen.call_count == 2
        assert urlopen.call_args_list[0].args[0] is urlopen.call_args_list[1].args[0]


def test_rate_limit_retries_are_bounded():
    errors = [
        HTTPError(
            WEBHOOK, 429, "rate limited", Message(), io.BytesIO(b'{"retry_after": 0.5}')
        )
        for _ in range(3)
    ]
    with (
        patch.object(announce_release, "urlopen", side_effect=errors) as urlopen,
        patch.object(announce_release.time, "sleep") as sleep,
    ):
        with pytest.raises(RuntimeError, match="Discord returned HTTP 429"):
            announce_release.send_announcement(WEBHOOK, "Release announcement")
        assert urlopen.call_count == 3
        assert sleep.call_count == 2
