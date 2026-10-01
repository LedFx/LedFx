"""The PR-title check in .github/scripts/pr_title.py (run by pr-title.yml)."""

import importlib.util
from pathlib import Path

import pytest

_path = Path(__file__).parents[1] / ".github" / "scripts" / "pr_title.py"
_spec = importlib.util.spec_from_file_location("pr_title", _path)
assert _spec and _spec.loader
pr_title = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pr_title)


@pytest.mark.parametrize(
    "title",
    [
        "feat: add Snapcast client as an audio source",
        "fix(api): keep blocking network calls off the event loop",
        "fix(api)!: remove two broken v1 routes",
        "chore(deps): update dependency ruff to v0.16.8",
        "chore(main): release 2.2.0",
    ],
)
def test_valid_titles(title):
    assert pr_title.VALID.match(title)


@pytest.mark.parametrize(
    ("title", "suggestion"),
    [
        (
            "Fix: MacOS tray icon thread requirements",
            "fix: MacOS tray icon thread requirements",
        ),
        ("Feat: Add melbank flag", "feat: add melbank flag"),
        (
            "Feat(dmx_input): pause/mute controls",
            "feat(dmx_input): pause/mute controls",
        ),
        (
            "fix noqa: SIM118 (iterate dict directly)",
            "fix(noqa): SIM118 (iterate dict directly)",
        ),
        ("Add support for LIFX Mirror", "feat: add support for LIFX Mirror"),
        (
            "Fix inactive audio device change events",
            "fix: inactive audio device change events",
        ),
        ("[Bugfix] crash on start.", "fix: crash on start"),
        ("doc: loopback on raspberry", "docs: loopback on raspberry"),
        ("fix:missing space", "fix: missing space"),
        ("WIP: Feature - venues", "feat: venues"),
        ("NowPlaying/extend", "feat: NowPlaying/extend"),
    ],
)
def test_invalid_titles_get_a_valid_suggestion(title, suggestion):
    assert not pr_title.VALID.match(title)
    assert pr_title.suggest(title) == suggestion
    assert pr_title.VALID.match(suggestion)


def test_comment_cannot_be_escaped_by_the_title():
    body = pr_title.comment("````\n@everyone <img src=x>")
    assert body.startswith(pr_title.MARKER)
    assert "`````text\n````\n@everyone" in body
