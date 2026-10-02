"""Domain errors raised by managers; v1 and v2 map them to HTTP responses."""

from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from ledfx.core import LedFxCore


class LedFxError(Exception):
    """Base domain error: an HTTP status, a Problem type suffix and a title."""

    status: ClassVar[int] = 500
    problem: ClassVar[str] = "internal"
    title: ClassVar[str] = "Internal error"

    def __init__(self, detail: str, *, loc: tuple[str | int, ...] = ()) -> None:
        super().__init__(detail)
        self.detail = detail
        self.loc = loc


class NotFound(LedFxError):
    status: ClassVar[int] = 404
    problem: ClassVar[str] = "not-found"
    title: ClassVar[str] = "Not found"

    def __init__(self, kind: str, id: str) -> None:
        super().__init__(f"{kind} '{id}' not found")
        self.kind = kind
        self.id = id

    def __reduce__(self):
        return type(self), (self.kind, self.id)


class Conflict(LedFxError):
    status: ClassVar[int] = 409
    problem: ClassVar[str] = "conflict"
    title: ClassVar[str] = "Conflict"


class Invalid(LedFxError):
    status: ClassVar[int] = 422
    problem: ClassVar[str] = "validation"
    title: ClassVar[str] = "Validation failed"


class Unavailable(LedFxError):
    status: ClassVar[int] = 503
    problem: ClassVar[str] = "unavailable"
    title: ClassVar[str] = "Unavailable"

    def __init__(self, feature: str) -> None:
        super().__init__(f"{feature} is not available")
        self.feature = feature

    def __reduce__(self):
        return type(self), (self.feature,)


class SafeMode(LedFxError):
    status: ClassVar[int] = 409
    problem: ClassVar[str] = "safe-mode"
    title: ClassVar[str] = "Safe mode"

    def __init__(self, reason: str) -> None:
        super().__init__(f"Config changes are disabled in safe mode: {reason}")
        self.reason = reason

    def __reduce__(self):
        return type(self), (self.reason,)


def ensure_writable(ledfx: "LedFxCore") -> None:
    """Raise SafeMode before a change that could never be saved."""
    store = ledfx.config_store
    if store.read_only:
        raise SafeMode(store.error or "config is read-only")
