"""The mapping from exceptions to RFC 9457 problems."""

import json
import re

import pytest
from aiohttp import web
from pydantic import BaseModel, ValidationError

from ledfx.api.v2.core.problem import (
    PROBLEM_PREFIX,
    Problem,
    ProblemDetailError,
    ProblemError,
    new_instance,
    problem_for,
    problem_headers,
    problem_response,
    validation_errors,
    validation_problem,
)
from ledfx.errors import (
    Conflict,
    Invalid,
    LedFxError,
    NotFound,
    SafeMode,
    Unavailable,
)


class _Body(BaseModel):
    count: int


def _validation_error() -> ValidationError:
    with pytest.raises(ValidationError) as info:
        _Body.model_validate({"count": "many"})
    return info.value


@pytest.mark.parametrize(
    ("exc", "status", "suffix", "detail"),
    [
        (
            NotFound("Virtual", "kitchen"),
            404,
            "not-found",
            "Virtual 'kitchen' not found",
        ),
        (Conflict("Preset is built in"), 409, "conflict", "Preset is built in"),
        (Invalid("Bad segment"), 422, "validation", "Bad segment"),
        (Unavailable("sendspin"), 503, "unavailable", Unavailable("sendspin").detail),
        (
            SafeMode("config.json is invalid"),
            409,
            "safe-mode",
            "Config changes are disabled in safe mode: config.json is invalid",
        ),
    ],
)
def test_domain_errors_keep_status_suffix_and_detail(
    exc: LedFxError, status: int, suffix: str, detail: str
) -> None:
    problem = problem_for(exc, "req-00000000")
    assert problem.status == status
    assert problem.type == PROBLEM_PREFIX + suffix
    assert problem.title == exc.title
    assert problem.detail == detail
    assert problem.instance == "req-00000000"
    assert problem.errors is None


def test_invalid_with_a_loc_names_it_in_errors() -> None:
    problem = problem_for(Invalid("Too long", loc=("body", "name")), "req-1")
    assert problem.errors == [
        ProblemDetailError(loc=["body", "name"], msg="Too long", type="validation")
    ]


def test_validation_problem_is_422_with_pydantic_errors_and_no_input() -> None:
    problem = problem_for(
        validation_problem(validation_errors(_validation_error())), "req-1"
    )
    assert problem.status == 422
    assert problem.type == PROBLEM_PREFIX + "validation"
    assert problem.detail == "1 invalid value(s)"
    assert problem.errors is not None
    assert [e.loc for e in problem.errors] == [["count"]]
    assert problem.errors[0].type == "int_parsing"
    assert "many" not in problem.model_dump_json()


def test_an_escaped_validation_error_is_a_500_without_field_names() -> None:
    problem = problem_for(_validation_error(), "req-1")
    assert (problem.status, problem.detail) == (500, "Internal error")
    assert problem.errors is None
    assert "count" not in problem.model_dump_json()


def test_validation_errors_prefixes_locs() -> None:
    errors = validation_errors(_validation_error(), ("body", "config"))
    assert [e.loc for e in errors] == [["body", "config", "count"]]


@pytest.mark.parametrize(
    ("exc", "status", "suffix"),
    [
        (web.HTTPBadRequest(), 400, "malformed"),
        (web.HTTPNotFound(), 404, "not-found"),
        (web.HTTPMethodNotAllowed("PUT", ["GET"]), 405, "method-not-allowed"),
        (web.HTTPRequestEntityTooLarge(max_size=1, actual_size=2), 413, "too-large"),
        (web.HTTPUnsupportedMediaType(), 415, "unsupported-media-type"),
        (web.HTTPTooManyRequests(), 429, "rate-limited"),
        (web.HTTPForbidden(), 403, "malformed"),
        (web.HTTPServiceUnavailable(), 503, "internal"),
    ],
)
def test_http_exceptions_keep_their_status(
    exc: web.HTTPException, status: int, suffix: str
) -> None:
    problem = problem_for(exc, "req-1")
    assert (problem.status, problem.type) == (status, PROBLEM_PREFIX + suffix)
    assert problem.detail == exc.reason


def test_unlisted_http_statuses_are_titled_by_their_standard_phrase() -> None:
    forbidden = problem_for(web.HTTPForbidden(), "req-1")
    assert forbidden.title == "Forbidden"
    unavailable = problem_for(web.HTTPServiceUnavailable(), "req-1")
    assert unavailable.title == "Service Unavailable"
    assert problem_for(web.HTTPNotFound(), "req-1").title == "Not found"


def test_method_not_allowed_keeps_the_allow_header() -> None:
    exc = web.HTTPMethodNotAllowed("PUT", ["GET", "POST"])
    assert problem_headers(exc) == {"Allow": "GET,POST"}
    assert problem_headers(web.HTTPNotFound()) == {}


def test_problem_error_passes_through() -> None:
    errors = [ProblemDetailError(loc=["query", "n"], msg="bad", type="int_parsing")]
    exc = ProblemError(422, "validation", "Validation failed", "1 bad", errors)
    problem = problem_for(exc, "req-1")
    assert (problem.status, problem.detail, problem.errors) == (422, "1 bad", errors)


def test_anything_else_is_500_without_the_exception_text() -> None:
    problem = problem_for(RuntimeError("secret path /home/x"), "req-1")
    assert problem.status == 500
    assert problem.type == PROBLEM_PREFIX + "internal"
    assert problem.detail == "Internal error"
    assert "secret" not in problem.model_dump_json()


def test_instance_ids_are_req_plus_8_hex() -> None:
    ids = {new_instance() for _ in range(20)}
    assert all(re.fullmatch(r"req-[0-9a-f]{8}", i) for i in ids)
    assert len(ids) > 1


def test_problem_response_is_problem_json_without_null_errors() -> None:
    problem = Problem(
        type=PROBLEM_PREFIX + "not-found",
        title="Not found",
        status=404,
        detail="x",
        instance="req-1",
    )
    response = problem_response(problem, {"Allow": "GET"})
    assert response.status == 404
    assert response.content_type == "application/problem+json"
    assert response.headers["Allow"] == "GET"
    assert json.loads(response.text or "") == {
        "type": "urn:ledfx:problem:not-found",
        "title": "Not found",
        "status": 404,
        "detail": "x",
        "instance": "req-1",
    }
