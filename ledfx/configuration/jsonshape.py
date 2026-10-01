"""Narrow untyped JSON values without raising (bad input becomes empty)."""


def as_dict(value: object) -> dict[str, object]:
    """The value if it is a JSON object, else a detached {} (the old code crashed)."""
    return value if isinstance(value, dict) else {}


def as_list(value: object) -> list[object]:
    """The value if it is a JSON array, else a detached []."""
    return value if isinstance(value, list) else []
