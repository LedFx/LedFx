"""Shared metadata normalisation helpers for the Now Playing subsystem.

These functions clean up noisy metadata that originates from YouTube /
YouTube Music via SMTC — artist channel names, video-title suffixes, and
placeholder album values.

Used by:
- ledfx.nowplaying.album_art.musicbrainz  (before MusicBrainz queries)
- ledfx.nowplaying.service                (before displaying track text on LEDs)
"""

import re

# ---- Compiled patterns --------------------------------------------------

# YouTube auto-generated channel: "Porter Robinson - Topic"
_TOPIC_RE = re.compile(r"\s*-\s*topic\s*$", re.IGNORECASE)

# YouTube artist channel: "MimiWebbVEVO", "ValleyVEVO"
_VEVO_RE = re.compile(r"vevo\s*$", re.IGNORECASE)

# Other common official/channel suffixes seen in YouTube SMTC metadata.
# e.g. "Zara Larsson Music" -> "Zara Larsson"
_ARTIST_CHANNEL_SUFFIX_RE = re.compile(
    r"\s*(?:official|music|records|recordings|entertainment|channel|tv)\s*$",
    re.IGNORECASE,
)

# Common YouTube video-title suffixes wrapped in parentheses or brackets.
# Matches any bracketed suffix that contains "official" or "video" anywhere,
# or is a standalone noise word (lyrics, visualiser, audio).
_TITLE_NOISE_RE = re.compile(
    r"\s*[\(\[]"
    r"\s*(?:[^\)\]]*\bofficial\b[^\)\]]*"
    r"|[^\)\]]*\bvideo\b[^\)\]]*"
    r"|lyrics?"
    r"|visuali[zs]er?"
    r"|audio"
    r")\s*[\)\]]\s*$",
    re.IGNORECASE,
)

# Quality/resolution tags that YouTube appends — these block other suffix
# patterns from being reached because they sit at the end of the string.
# e.g. "Starman (Official Video) [4K]" -> "Starman (Official Video)" (first
# pass), then "(Official Video)" is removed on the next iteration.
_QUALITY_TAG_RE = re.compile(
    r"\s*[\(\[]\s*"
    r"(?:\d{3,4}[pP]"  # 720p, 1080p, 4320p
    r"|[248][kK]"  # 4K, 2K, 8K
    r"|[hH][dD]"  # HD
    r"|[hH][qQ]"  # HQ
    r"|[fF][hH][dD]"  # FHD
    r"|[uU][hH][dD]"  # UHD
    r")"
    r"\s*[\)\]]\s*$",
    re.IGNORECASE,
)

# Version/remaster suffixes — MusicBrainz stores these separately and they
# add noise to both queries and LED display text.
# e.g. "In This Town (2018 Remastered)" -> "In This Town"
_VERSION_SUFFIX_RE = re.compile(
    r"\s*[\(\[]\s*"
    r"(?:"
    r"(?:\d{4}\s+)?remaster(?:ed)?"
    r"|remastered\s+version"
    r"|remaster(?:ed)?\s+\d{4}"
    r"|single\s+version"
    r"|album\s+version"
    r"|radio\s+edit"
    r"|edit"
    r")"
    r"\s*[\)\]]\s*$",
    re.IGNORECASE,
)

# Unbracketed "- Official Video" / "- Official Audio" / "- Lyric Video" etc.
# YouTube often appends these outside of parentheses.
_TITLE_UNBRACKETED_NOISE_RE = re.compile(
    r"\s*[-\u2013\u2014]\s*"
    r"(?:official\s+(?:video|audio|music\s+video|lyric\s+video|visuali[zs]er?)"
    r"|lyric\s+video"
    r"|lyrics?\s+video"
    r")\s*$",
    re.IGNORECASE,
)

# Collaboration connector words in normalised (lower-case, stripped) text.
# Used to detect "Artist x Feature", "Artist feat. Feature" etc. as an
# artist-prefix segment of a title.
_COLLAB_CONNECTOR_RE = re.compile(r"\b(?:feat|ft|x|and|with)\b")

# After stripping the artist prefix from a title, a YouTube channel-suffix
# token can be left at the start.
# e.g. "Topic - Missionary Man" after "Eurythmics - " was removed.
_TITLE_CHANNEL_PREFIX_RE = re.compile(
    r"^(?:topic|vevo)\s*[-\u2013\u2014]\s*",
    re.IGNORECASE,
)

# Album placeholder values that mean "no album".
_EMPTY_ALBUMS = {
    "",
    "unknown",
    "unknown album",
    "none",
    "n/a",
    "null",
}


# ---- Low-level helpers --------------------------------------------------


def _clean_spaces(value: str) -> str:
    """Collapse repeated whitespace and trim."""
    return re.sub(r"\s+", " ", value).strip()


def _normalise_compare(value: str | None) -> str:
    """Normalise a string for case-insensitive / punctuation-agnostic comparison.

    Returns a lower-case, ASCII-word-only string suitable for equality
    and fuzzy-similarity checks.
    """
    if not value:
        return ""
    value = value.lower()
    value = re.sub(r"['`\u00b4]", "'", value)
    value = re.sub(r"&", " and ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return _clean_spaces(value)


def _split_camel_case(value: str) -> str:
    """Insert spaces at camelCase boundaries.

    Examples::

        MimiWebb  -> Mimi Webb
        ABCArtist -> ABC Artist
    """
    value = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value)
    value = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", value)
    return value.strip()


def _strip_title_suffixes(title: str) -> str:
    """Iteratively strip known YouTube/version suffixes from the end of a title."""
    prev = None
    while prev != title:
        prev = title
        title = _QUALITY_TAG_RE.sub("", title).strip()
        title = _TITLE_NOISE_RE.sub("", title).strip()
        title = _TITLE_UNBRACKETED_NOISE_RE.sub("", title).strip()
        title = _VERSION_SUFFIX_RE.sub("", title).strip()
    return title


# ---- Public API ---------------------------------------------------------


def normalise_artist(artist: str | None) -> str:
    """Normalise a YouTube-style artist/channel name.

    Examples::

        ValleyVEVO               -> Valley
        MimiWebbVEVO             -> Mimi Webb
        Porter Robinson - Topic  -> Porter Robinson
        Zara Larsson Music       -> Zara Larsson
    """
    if not artist:
        return ""

    artist = _clean_spaces(artist)

    # Strip " - Topic" (YouTube auto-generated topic channels)
    artist = _TOPIC_RE.sub("", artist).strip()

    # Strip VEVO suffix; if the remainder has no spaces it was a concatenated
    # channel name like "MimiWebb" — split on camelCase boundaries.
    if _VEVO_RE.search(artist):
        artist = _VEVO_RE.sub("", artist).strip()
        if " " not in artist:
            artist = _split_camel_case(artist)

    # Strip repeated generic channel suffixes ("Music", "Official", etc.)
    prev = None
    while prev != artist:
        prev = artist
        artist = _ARTIST_CHANNEL_SUFFIX_RE.sub("", artist).strip()

    # Last-resort split for any remaining concatenated name without spaces.
    if " " not in artist:
        artist = _split_camel_case(artist)

    return _clean_spaces(artist)


def normalise_title(title: str | None, artist: str = "") -> str:
    """Remove YouTube/video/release noise from a track title.

    Examples::

        Mimi Webb - Erase You (Official Music Video)      -> Erase You
        Song Name [Official Video]                        -> Song Name
        In This Town (2018 Remastered)                    -> In This Town
        Eurythmics - Topic - Missionary Man (2018 Rem...) -> Missionary Man
    """
    if not title:
        return ""

    title = _clean_spaces(title)
    artist = normalise_artist(artist)

    title = _strip_title_suffixes(title)

    # Remove redundant leading "Artist - " / "Artist – " / "Artist: " prefix.
    if artist:
        title = re.sub(
            rf"^{re.escape(artist)}\s*[-\u2013\u2014:]\s*",
            "",
            title,
            flags=re.IGNORECASE,
        ).strip()

    # Fallback: split on first " - " and check if the left segment matches
    # the artist after normalisation (handles camelCase/VEVO channel names,
    # or collaboration credits like "Artist x Feature - Title").
    parts = re.split(r"\s+[-\u2013\u2014]\s+", title, maxsplit=1)
    if len(parts) == 2:
        left = normalise_artist(parts[0])
        if artist and _normalise_compare(left) == _normalise_compare(artist):
            title = parts[1].strip()
        elif artist:
            # Handle "Campbell x Alcemist - Title" where artist is "Campbell":
            # left part starts with the artist and contains a collab connector.
            left_cmp = _normalise_compare(parts[0])
            artist_cmp = _normalise_compare(artist)
            suffix = left_cmp[len(artist_cmp) :]
            if left_cmp.startswith(
                artist_cmp + " "
            ) and _COLLAB_CONNECTOR_RE.search(suffix):
                title = parts[1].strip()

    # Strip any residual YouTube channel-suffix token at the front, e.g.
    # "Topic - Missionary Man" left after "Eurythmics - " was removed.
    title = _TITLE_CHANNEL_PREFIX_RE.sub("", title).strip()

    title = _strip_title_suffixes(title)
    return _clean_spaces(title)


def normalise_album(album: str | None) -> str | None:
    """Return None for placeholder album values, otherwise the cleaned string.

    Examples::

        "Unknown album" -> None
        ""              -> None
        "Thriller"      -> "Thriller"
    """
    if album is None:
        return None
    album = _clean_spaces(album)
    if album.lower() in _EMPTY_ALBUMS:
        return None
    return album
