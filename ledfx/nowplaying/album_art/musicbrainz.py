"""MusicBrainz + Cover Art Archive album-art provider.

Uses publicly available, no-auth APIs:
- MusicBrainz recording search:  https://musicbrainz.org/ws/2/
- Cover Art Archive front cover: https://coverartarchive.org/release/{mbid}/front

No API keys or user accounts required.
"""

import logging
import re
import urllib.parse
from dataclasses import dataclass
from difflib import SequenceMatcher

import aiohttp

from ledfx.nowplaying.album_art.base import AlbumArtProvider
from ledfx.nowplaying.models import TrackMetadata
from ledfx.nowplaying.normalise import (
    _clean_spaces,
    _normalise_compare,
    normalise_album,
    normalise_artist,
    normalise_title,
)

_LOGGER = logging.getLogger(__name__)

_MB_SEARCH_URL = "https://musicbrainz.org/ws/2/recording/"
# Use the 500 px thumbnail — full-size images can exceed 10 MB while a 500 px
# JPEG is typically 50–200 KB, which is ample for gradient extraction and any
# LED matrix resolution.  CAA guarantees thumbnails exist whenever the image
# does: https://musicbrainz.org/doc/Cover_Art_Archive/API
_CAA_FRONT_URL = "https://coverartarchive.org/release/{mbid}/front-500"

# MusicBrainz requires a descriptive User-Agent per API policy:
# https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting
_USER_AGENT = "LedFx/1.0 (https://github.com/LedFx/LedFx)"

# Maximum number of recording results to inspect per search query
_MAX_RECORDINGS = 10

# Maximum number of scored release candidates to try against Cover Art Archive
_MAX_RELEASE_CANDIDATES = 20

# Per-request timeouts (seconds)
_SEARCH_TIMEOUT = 8
_ART_TIMEOUT = 10

# Terms that usually mean the recording/release is not the canonical track art.
_BAD_VARIANT_TERMS = {
    "acoustic",
    "commentary",
    "cover version",
    "demo",
    "dj beats",
    "dj mix",
    "dj-mix",
    "instrumental",
    "karaoke",
    "live",
    "mastermix",
    "original voicenote",
    "performance",
    "radio edit",
    "remix",
    "tribute",
    "voicenote",
}

# These are useful disambiguations, but they do not imply different cover art.
_NEUTRAL_VARIANT_TERMS = {
    "clean",
    "explicit",
}

# Release/secondary type values that tend to be poor cover-art sources.
_BAD_RELEASE_TYPES = {
    "compilation",
    "dj-mix",
    "interview",
    "live",
    "mixtape/street",
    "remix",
    "soundtrack",
    "spokenword",
}

_VARIOUS_ARTISTS_TERMS = {
    "various artists",
    "various",
}


@dataclass(slots=True)
class _ReleaseCandidate:
    """A release MBID with a score explaining how promising it is."""

    score: float
    mbid: str
    recording_title: str
    release_title: str
    recording_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class _ScoringRules:
    """Centralized tunables for MusicBrainz scoring heuristics."""

    bad_variant_terms: frozenset[str]
    neutral_variant_terms: frozenset[str]
    bad_release_types: frozenset[str]
    various_artists_terms: frozenset[str]

    # Recording-level scoring
    title_similarity_weight: float = 45
    exact_title_bonus: float = 40
    artist_similarity_weight: float = 35
    exact_artist_bonus: float = 30
    video_penalty: float = 70
    bad_recording_variant_penalty: float = 90
    neutral_disambiguation_bonus: float = 2

    # Release-level scoring
    release_title_similarity_weight: float = 20
    release_title_exact_bonus: float = 30
    album_similarity_weight: float = 25
    album_exact_bonus: float = 25
    bad_release_title_penalty: float = 80
    release_artist_similarity_weight: float = 55
    release_artist_exact_bonus: float = 45
    release_artist_mismatch_threshold: float = 0.45
    release_artist_mismatch_penalty: float = 70
    various_artists_penalty: float = 70
    single_bonus: float = 22
    album_bonus: float = 12
    ep_bonus: float = 8
    bad_release_type_penalty: float = 80
    official_status_bonus: float = 8
    non_official_status_penalty: float = 4
    has_date_bonus: float = 1


_SCORING_RULES = _ScoringRules(
    bad_variant_terms=frozenset(_BAD_VARIANT_TERMS),
    neutral_variant_terms=frozenset(_NEUTRAL_VARIANT_TERMS),
    bad_release_types=frozenset(_BAD_RELEASE_TYPES),
    various_artists_terms=frozenset(_VARIOUS_ARTISTS_TERMS),
)


def _contains_bad_variant(value: str | None) -> bool:
    """Return True if *value* contains a strong non-canonical variant term."""
    text = _normalise_compare(value)
    if not text:
        return False

    for term in _SCORING_RULES.bad_variant_terms:
        term_text = _normalise_compare(term)
        if not term_text:
            continue
        if re.search(rf"\b{re.escape(term_text)}\b", text):
            return True
    return False


def _contains_neutral_variant(value: str | None) -> bool:
    """Return True if *value* contains clean/explicit style disambiguation."""
    text = _normalise_compare(value)
    if not text:
        return False

    return any(
        _normalise_compare(term) in text
        for term in _SCORING_RULES.neutral_variant_terms
    )


def _similarity(left: str | None, right: str | None) -> float:
    """Return a simple 0..1 fuzzy similarity score."""
    left_cmp = _normalise_compare(left)
    right_cmp = _normalise_compare(right)
    if not left_cmp or not right_cmp:
        return 0.0
    if left_cmp == right_cmp:
        return 1.0
    return SequenceMatcher(None, left_cmp, right_cmp).ratio()


def _artist_credit_text(recording: dict) -> str:
    """Flatten a MusicBrainz artist-credit list to display text."""
    credits = recording.get("artist-credit") or []
    parts: list[str] = []

    for credit in credits:
        if isinstance(credit, dict):
            if name := credit.get("name"):
                parts.append(name)
            if joinphrase := credit.get("joinphrase"):
                parts.append(joinphrase)
        elif isinstance(credit, str):
            parts.append(credit)

    return _clean_spaces("".join(parts))


def _release_group_types(release: dict) -> set[str]:
    """Return lower-case primary/secondary release-group type names."""
    group = release.get("release-group") or {}
    values: set[str] = set()

    primary = group.get("primary-type")
    if primary:
        values.add(str(primary).lower())

    for secondary in group.get("secondary-types") or []:
        values.add(str(secondary).lower())

    return values


def _looks_like_various_artists(value: str | None) -> bool:
    """Return True for typical various-artists credit labels."""
    text = _normalise_compare(value)
    if not text:
        return False
    return any(term in text for term in _SCORING_RULES.various_artists_terms)


def _recording_score(
    recording: dict, artist: str, title: str
) -> tuple[float, list[str]]:
    """Score a MusicBrainz recording result before release-level scoring."""
    score = float(recording.get("score") or 0)
    reasons = [f"mb_score={score:g}"]

    recording_title = recording.get("title") or ""
    title_similarity = _similarity(recording_title, title)
    score += title_similarity * _SCORING_RULES.title_similarity_weight
    reasons.append(f"title_sim={title_similarity:.2f}")

    if _normalise_compare(recording_title) == _normalise_compare(title):
        score += _SCORING_RULES.exact_title_bonus
        reasons.append("exact_title")

    artist_text = _artist_credit_text(recording)
    artist_similarity = _similarity(artist_text, artist)
    score += artist_similarity * _SCORING_RULES.artist_similarity_weight
    reasons.append(f"artist_sim={artist_similarity:.2f}")

    if _normalise_compare(artist_text) == _normalise_compare(artist):
        score += _SCORING_RULES.exact_artist_bonus
        reasons.append("exact_artist")

    if recording.get("video") is True:
        score -= _SCORING_RULES.video_penalty
        reasons.append("video_penalty")

    disambiguation = recording.get("disambiguation") or ""
    combined = f"{recording_title} {disambiguation}"

    if _contains_bad_variant(combined):
        score -= _SCORING_RULES.bad_recording_variant_penalty
        reasons.append("bad_recording_variant")

    if _contains_neutral_variant(disambiguation):
        score += _SCORING_RULES.neutral_disambiguation_bonus
        reasons.append("neutral_disambiguation")

    return score, reasons


def _release_score(
    release: dict,
    base_score: float,
    base_reasons: list[str],
    artist: str,
    title: str,
    album: str | None,
) -> tuple[float, str]:
    """Add release-specific scoring to a recording score."""
    score = base_score
    reasons = list(base_reasons)

    release_title = release.get("title") or ""

    release_title_similarity = _similarity(release_title, title)
    score += (
        release_title_similarity
        * _SCORING_RULES.release_title_similarity_weight
    )
    reasons.append(f"release_title_sim={release_title_similarity:.2f}")

    # A single commonly has the same title as the track.
    if _normalise_compare(release_title) == _normalise_compare(title):
        score += _SCORING_RULES.release_title_exact_bonus
        reasons.append("release_title_exact")

    if album:
        album_similarity = _similarity(release_title, album)
        score += album_similarity * _SCORING_RULES.album_similarity_weight
        reasons.append(f"album_sim={album_similarity:.2f}")
        if _normalise_compare(release_title) == _normalise_compare(album):
            score += _SCORING_RULES.album_exact_bonus
            reasons.append("album_exact")

    if _contains_bad_variant(release_title):
        score -= _SCORING_RULES.bad_release_title_penalty
        reasons.append("bad_release_title_variant")

    # Strongly prefer releases whose credited artist matches the track artist.
    release_artist = _artist_credit_text(release)
    candidate_artist = release_artist

    if candidate_artist:
        artist_similarity = _similarity(candidate_artist, artist)
        score += (
            artist_similarity * _SCORING_RULES.release_artist_similarity_weight
        )
        reasons.append(f"release_artist_sim={artist_similarity:.2f}")

        if _normalise_compare(candidate_artist) == _normalise_compare(artist):
            score += _SCORING_RULES.release_artist_exact_bonus
            reasons.append("release_artist_exact")
        elif (
            artist_similarity
            < _SCORING_RULES.release_artist_mismatch_threshold
        ):
            score -= _SCORING_RULES.release_artist_mismatch_penalty
            reasons.append("release_artist_mismatch")

        if _looks_like_various_artists(candidate_artist):
            score -= _SCORING_RULES.various_artists_penalty
            reasons.append("various_artists")

    group_types = _release_group_types(release)

    if "single" in group_types:
        score += _SCORING_RULES.single_bonus
        reasons.append("single")
    if "album" in group_types:
        score += _SCORING_RULES.album_bonus
        reasons.append("album")
    if "ep" in group_types:
        score += _SCORING_RULES.ep_bonus
        reasons.append("ep")

    bad_types = group_types.intersection(_SCORING_RULES.bad_release_types)
    if bad_types:
        score -= _SCORING_RULES.bad_release_type_penalty
        reasons.append(f"bad_release_type={','.join(sorted(bad_types))}")

    # Official releases are preferred over bootlegs/promos when available.
    status = str(release.get("status") or "").lower()
    if status == "official":
        score += _SCORING_RULES.official_status_bonus
        reasons.append("official")
    elif status:
        score -= _SCORING_RULES.non_official_status_penalty
        reasons.append(f"status={status}")

    # Country/date are not hard requirements, but complete metadata tends to
    # indicate a better release candidate.
    if release.get("date"):
        score += _SCORING_RULES.has_date_bonus

    return score, ",".join(reasons)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    """Remove duplicate strings while preserving order."""
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)

    return result


def _mb_quote(value: str) -> str:
    """Escape a string for a quoted MusicBrainz query value."""
    return value.replace("\\", "\\\\").replace('"', r'\"')


# ---- Provider -----------------------------------------------------------


class MusicBrainzArtProvider(AlbumArtProvider):
    """Resolve album art via MusicBrainz recording search + Cover Art Archive."""

    async def resolve(self, metadata: TrackMetadata) -> bytes | None:
        artist = normalise_artist(metadata.artist)
        title = normalise_title(metadata.title, artist)
        album = normalise_album(metadata.album)

        if not artist and not title:
            return None

        _LOGGER.debug(
            "MusicBrainz: normalised metadata — \nartist=%r \ntitle=%r \nalbum=%r",
            artist,
            title,
            album,
        )

        candidates = await self._search_release_candidates(
            artist, title, album
        )
        if not candidates:
            _LOGGER.debug(
                "MusicBrainz: no recordings found for artist=%r title=%r",
                artist,
                title,
            )
            return None

        for candidate in candidates[:_MAX_RELEASE_CANDIDATES]:
            _LOGGER.debug(
                "MusicBrainz: trying cover candidate score=%.1f release=%s "
                "recording=%r release_title=%r reason=%s",
                candidate.score,
                candidate.mbid,
                candidate.recording_title,
                candidate.release_title,
                candidate.reason,
            )

            data = await self._fetch_cover_art(candidate.mbid)
            if data:
                _LOGGER.info(
                    "MusicBrainz: resolved artwork for artist=%r title=%r "
                    "(release %s score %.1f)",
                    artist,
                    title,
                    candidate.mbid,
                    candidate.score,
                )
                return data

        _LOGGER.debug(
            "MusicBrainz: cover art not found for artist=%r title=%r",
            artist,
            title,
        )
        return None

    async def _search_release_candidates(
        self, artist: str, title: str, album: str | None
    ) -> list[_ReleaseCandidate]:
        """Query MusicBrainz and return scored release candidates.

        MusicBrainz result order is not good enough for cover art. For example,
        a DJ compilation or remix can appear before the canonical single. This
        method collects all release candidates from several lightweight queries
        and sorts them before any Cover Art Archive fetches happen.
        """
        recordings: list[dict] = []

        for query in self._build_queries(artist, title, album):
            data = await self._search_recordings(query)
            for recording in data:
                rid = recording.get("id")
                if rid and not any(
                    existing.get("id") == rid for existing in recordings
                ):
                    recordings.append(recording)

        candidates_by_release: dict[str, _ReleaseCandidate] = {}

        for recording in recordings:
            base_score, base_reasons = _recording_score(
                recording, artist, title
            )
            recording_title = recording.get("title") or ""
            recording_id = recording.get("id") or ""

            for release in recording.get("releases") or []:
                mbid = release.get("id")
                if not mbid:
                    continue

                release_title = release.get("title") or ""
                score, reason = _release_score(
                    release,
                    base_score,
                    base_reasons,
                    artist,
                    title,
                    album,
                )

                candidate = _ReleaseCandidate(
                    score=score,
                    mbid=mbid,
                    recording_title=recording_title,
                    release_title=release_title,
                    recording_id=recording_id,
                    reason=reason,
                )

                current = candidates_by_release.get(mbid)
                if current is None or candidate.score > current.score:
                    candidates_by_release[mbid] = candidate

        candidates = list(candidates_by_release.values())

        candidates.sort(key=lambda candidate: candidate.score, reverse=True)

        _LOGGER.debug(
            "MusicBrainz: built %d scored release candidates for artist=%r title=%r",
            len(candidates),
            artist,
            title,
        )

        return candidates

    def _build_queries(
        self, artist: str, title: str, album: str | None
    ) -> list[str]:
        """Build MusicBrainz recording search queries from strict to loose."""
        queries: list[str] = []

        parts: list[str] = []
        if title:
            parts.append(f'recording:"{_mb_quote(title)}"')
        if artist:
            parts.append(f'artistname:"{_mb_quote(artist)}"')
        if album:
            parts.append(f'release:"{_mb_quote(album)}"')
        if parts:
            queries.append(" AND ".join(parts))

        # Same without album. Album text from SMTC is often absent or noisy.
        parts = []
        if title:
            parts.append(f'recording:"{_mb_quote(title)}"')
        if artist:
            parts.append(f'artistname:"{_mb_quote(artist)}"')
        if parts:
            queries.append(" AND ".join(parts))

        # Looser query: fielded artist + unquoted title.
        parts = []
        if title:
            parts.append(title)
        if artist:
            parts.append(f'artistname:"{_mb_quote(artist)}"')
        if parts:
            queries.append(" AND ".join(parts))

        # Loosest fallback. This helps when MusicBrainz stores version/remaster
        # data differently from the SMTC title.
        if artist and title:
            queries.append(f"{artist} {title}")
        elif title:
            queries.append(title)

        return _dedupe_preserve_order(queries)

    async def _search_recordings(self, query: str) -> list[dict]:
        """Run a single MusicBrainz recording search query."""
        params = {
            "query": query,
            "fmt": "json",
            "limit": str(_MAX_RECORDINGS),
        }

        url = _MB_SEARCH_URL + "?" + urllib.parse.urlencode(params)

        _LOGGER.debug("MusicBrainz: search query=%r", query)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers={
                        "User-Agent": _USER_AGENT,
                        "Accept": "application/json",
                    },
                    timeout=aiohttp.ClientTimeout(total=_SEARCH_TIMEOUT),
                    allow_redirects=True,
                ) as resp:
                    if resp.status != 200:
                        _LOGGER.debug(
                            "MusicBrainz search returned HTTP %d for query=%r",
                            resp.status,
                            query,
                        )
                        return []
                    data = await resp.json(content_type=None)
        except Exception as exc:
            _LOGGER.warning(
                "MusicBrainz search failed for query=%r: %s", query, exc
            )
            return []

        return data.get("recordings") or []

    async def _fetch_cover_art(self, mbid: str) -> bytes | None:
        """Fetch the front cover for a release from Cover Art Archive."""
        url = _CAA_FRONT_URL.format(mbid=mbid)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers={"User-Agent": _USER_AGENT},
                    timeout=aiohttp.ClientTimeout(total=_ART_TIMEOUT),
                    allow_redirects=True,
                ) as resp:
                    if resp.status != 200:
                        return None
                    return await resp.read()
        except Exception as exc:
            _LOGGER.debug(
                "Cover Art Archive fetch failed for %s: %s", mbid, exc
            )
            return None
