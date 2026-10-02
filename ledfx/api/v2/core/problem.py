"""RFC 9457 problem responses for /api/v2."""

import secrets
from collections.abc import Mapping
from http import HTTPStatus

from aiohttp import web
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic_core import from_json

from ledfx.errors import LedFxError

PROBLEM_PREFIX = "urn:ledfx:problem:"
PROBLEM_MEDIA_TYPE = "application/problem+json"

# Titles for the problems aiohttp and the framework raise; domain errors carry
# their own. Keys are the problem type suffixes (urn:ledfx:problem:<suffix>).
_TITLES = {
    "malformed": "Malformed request",
    "not-found": "Not found",
    "method-not-allowed": "Method not allowed",
    "too-large": "Request too large",
    "unsupported-media-type": "Unsupported media type",
    "validation": "Validation failed",
    "rate-limited": "Rate limited",
    "internal": "Internal error",
}
_HTTP_SUFFIXES = {
    400: "malformed",
    404: "not-found",
    405: "method-not-allowed",
    413: "too-large",
    415: "unsupported-media-type",
    429: "rate-limited",
}


class ProblemDetailError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    loc: list[str | int]
    msg: str
    type: str


class Problem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    detail: str
    instance: str
    errors: list[ProblemDetailError] | None = None


class ProblemError(Exception):
    """Raised by the framework for a problem it has already classified."""

    def __init__(
        self,
        status: int,
        suffix: str,
        title: str,
        detail: str,
        errors: list[ProblemDetailError] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.suffix = suffix
        self.title = title
        self.detail = detail
        self.errors = errors


def new_instance() -> str:
    """A request id for Problem.instance and the log line: req- + 8 hex."""
    return f"req-{secrets.token_hex(4)}"


def validation_errors(
    err: ValidationError, prefix: tuple[str | int, ...] = ()
) -> list[ProblemDetailError]:
    """pydantic's errors as Problem errors, each loc prefixed (e.g. "body").
    Inputs are left out: they can be large, and the client sent them."""
    return [
        ProblemDetailError(loc=[*prefix, *e["loc"]], msg=e["msg"], type=e["type"])
        for e in err.errors(
            include_url=False, include_context=False, include_input=False
        )
    ]


MAX_PROBLEM_ERRORS = 100  # a big body must not make a bigger response


def validation_problem(errors: list[ProblemDetailError]) -> ProblemError:
    detail = f"{len(errors)} invalid value(s)"
    if len(errors) > MAX_PROBLEM_ERRORS:
        detail += f" (first {MAX_PROBLEM_ERRORS} of {len(errors)} errors)"
        errors = errors[:MAX_PROBLEM_ERRORS]
    return ProblemError(422, "validation", _TITLES["validation"], detail, errors)


def json_body(raw: bytes) -> object:
    """Parse a request body. Invalid JSON, absurd nesting and NaN or Infinity
    (which the JSON standard lacks and a typed contract cannot hold) are a 400."""
    try:
        return from_json(raw, allow_inf_nan=False)
    except ValueError:
        raise ProblemError(
            400,
            "malformed",
            _TITLES["malformed"],
            "The request body is not valid JSON",
        ) from None


def _problem(
    status: int,
    suffix: str,
    title: str,
    detail: str,
    instance: str,
    errors: list[ProblemDetailError] | None = None,
) -> Problem:
    return Problem(
        type=PROBLEM_PREFIX + suffix,
        title=title,
        status=status,
        detail=detail,
        instance=instance,
        errors=errors,
    )


def problem_for(exc: BaseException, instance: str) -> Problem:
    """Any exception as a Problem."""
    if isinstance(exc, ProblemError):
        return _problem(
            exc.status, exc.suffix, exc.title, exc.detail, instance, exc.errors
        )
    if isinstance(exc, LedFxError):
        errors = None
        if exc.loc and exc.status == 422:
            errors = [
                ProblemDetailError(loc=list(exc.loc), msg=exc.detail, type=exc.problem)
            ]
        return _problem(
            exc.status, exc.problem, exc.title, exc.detail, instance, errors
        )
    # A ValidationError is not mapped: the binder reports request errors itself,
    # so one reaching here is the server's own (stored config, a built model)
    # and falls through to the logged 500.
    if isinstance(exc, web.HTTPException):
        # An HTTP status not in _HTTP_SUFFIXES keeps its code and its standard
        # phrase as the title, and borrows the nearest suffix; add a row to
        # _HTTP_SUFFIXES when v2 raises one.
        if exc.status in _HTTP_SUFFIXES:
            suffix = _HTTP_SUFFIXES[exc.status]
            title = _TITLES[suffix]
        else:
            suffix = "malformed" if exc.status < 500 else "internal"
            title = HTTPStatus(exc.status).phrase
        return _problem(exc.status, suffix, title, exc.reason, instance)
    return _problem(500, "internal", _TITLES["internal"], "Internal error", instance)


def problem_headers(exc: BaseException) -> dict[str, str]:
    """Headers a Problem must keep from the exception: Allow on a 405."""
    if isinstance(exc, web.HTTPMethodNotAllowed):
        return {"Allow": exc.headers["Allow"]}
    return {}


def problem_response(
    problem: Problem, headers: Mapping[str, str] | None = None
) -> web.Response:
    return web.Response(
        status=problem.status,
        text=problem.model_dump_json(exclude_none=True),
        content_type=PROBLEM_MEDIA_TYPE,
        headers=headers,
    )
