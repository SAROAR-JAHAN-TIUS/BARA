"""
BARA Backend – Mismatch Detector.

Compares frontend API calls against backend endpoints and produces Issues.
"""
from __future__ import annotations
from typing import List, Optional

from app.models.analysis import ApiCall, ApiEndpoint, Issue, Location
from app.analyzers.normalizer import normalize_path, paths_match


# ---------------------------------------------------------------------------
# Beginner-friendly explanation templates
# ---------------------------------------------------------------------------

_EXPLANATIONS = {
    "MISSING_BACKEND_ENDPOINT": (
        "The frontend is trying to call {method} {path}, but no matching endpoint "
        "exists in the backend. This is like calling a phone number that nobody "
        "answers — the request is sent, but nothing on the other side handles it. "
        "The browser (or user) will receive a 404 Not Found error."
    ),
    "METHOD_MISMATCH": (
        "The frontend is sending a {fe_method} request to {path}, but the backend "
        "endpoint at {path} only accepts {be_method} requests. Think of this like "
        "knocking on a door vs. ringing a doorbell — both actions are directed at "
        "the same address, but the backend is only listening for one of them."
    ),
    "REQUEST_FIELD_MISMATCH": (
        "The frontend is sending a field called '{fe_field}' in the request body, "
        "but the backend expects a field called '{be_field}'. The backend will "
        "either ignore the frontend's field or fail validation. It is like filling "
        "out a form with the wrong label — the server cannot read what you sent."
    ),
    "RESPONSE_FIELD_MISMATCH": (
        "The frontend is trying to read a field called '{fe_field}' from the "
        "backend's response, but the backend returns a field called '{be_field}'. "
        "The frontend will receive `undefined` instead of the expected data."
    ),
    "QUERY_PARAM_MISMATCH": (
        "The frontend is sending a query parameter called '{fe_param}' (e.g. "
        "?{fe_param}=value), but the backend does not declare that parameter. "
        "The backend may ignore the parameter or return unexpected results."
    ),
    "PATH_MISMATCH": (
        "The frontend is requesting {fe_path}, but the closest backend route is "
        "{be_path}. Both sides exist but they are not using the same address — "
        "similar to having the wrong street name while the house number is right."
    ),
}

_FIXES = {
    "MISSING_BACKEND_ENDPOINT": (
        "Add a {method} endpoint at {path} to the backend, or update the frontend "
        "to call an existing backend endpoint."
    ),
    "METHOD_MISMATCH": (
        "Change the frontend request method from {fe_method} to {be_method}, or "
        "change the backend decorator from @app.{be_method_lower}('{path}') to "
        "@app.{fe_method_lower}('{path}')."
    ),
    "REQUEST_FIELD_MISMATCH": (
        "Rename the field in the frontend from '{fe_field}' to '{be_field}', or "
        "rename the field in the backend Pydantic model from '{be_field}' to "
        "'{fe_field}'."
    ),
    "RESPONSE_FIELD_MISMATCH": (
        "Update the frontend to use '{be_field}' instead of '{fe_field}', or "
        "rename the backend response field from '{be_field}' to '{fe_field}'."
    ),
    "QUERY_PARAM_MISMATCH": (
        "Add '{fe_param}' as a query parameter in the backend route function, or "
        "update the frontend to use the correct parameter name."
    ),
    "PATH_MISMATCH": (
        "Change the frontend to call {be_path} instead of {fe_path}, or rename "
        "the backend route from {be_path} to {fe_path}."
    ),
}


def _fmt(template: str, **kwargs) -> str:
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


def _find_matching_endpoint(
    call: ApiCall,
    endpoints: List[ApiEndpoint],
    same_method: bool = True,
) -> Optional[ApiEndpoint]:
    """Return the first endpoint whose path matches *call*.

    If *same_method* is True, also require matching HTTP method.
    """
    norm_call = normalize_path(call.path)
    for ep in endpoints:
        if paths_match(call.path, ep.path):
            if same_method and ep.method.upper() != call.method.upper():
                continue
            return ep
    return None


def _find_endpoint_any_method(
    call: ApiCall, endpoints: List[ApiEndpoint]
) -> Optional[ApiEndpoint]:
    """Return any endpoint with the same (normalized) path regardless of method."""
    for ep in endpoints:
        if paths_match(call.path, ep.path):
            return ep
    return None


def detect_mismatches(
    frontend_calls: List[ApiCall],
    backend_endpoints: List[ApiEndpoint],
) -> List[Issue]:
    issues: List[Issue] = []

    for call in frontend_calls:
        fe_loc = Location(file=call.source_file, line=call.line_number)

        # 1. Try to find an exact match (path + method)
        exact = _find_matching_endpoint(call, backend_endpoints, same_method=True)
        if exact:
            # Check request field mismatches
            if call.body_fields and exact.request_fields:
                fe_set = set(call.body_fields)
                be_set = set(exact.request_fields)
                only_in_fe = fe_set - be_set
                only_in_be = be_set - fe_set
                for fe_field in only_in_fe:
                    # Find a plausible "expected" backend field
                    be_candidate = next(iter(only_in_be), "?")
                    be_loc = Location(file=exact.source_file, line=exact.line_number)
                    issues.append(
                        Issue(
                            issue_type="REQUEST_FIELD_MISMATCH",
                            severity="high",
                            frontend_location=fe_loc,
                            backend_location=be_loc,
                            expected=be_candidate,
                            actual=fe_field,
                            explanation=_fmt(
                                _EXPLANATIONS["REQUEST_FIELD_MISMATCH"],
                                fe_field=fe_field,
                                be_field=be_candidate,
                            ),
                            suggested_fix=_fmt(
                                _FIXES["REQUEST_FIELD_MISMATCH"],
                                fe_field=fe_field,
                                be_field=be_candidate,
                            ),
                        )
                    )

            # Check response field mismatches
            if call.response_fields and exact.response_fields:
                fe_set = set(call.response_fields)
                be_set = set(exact.response_fields)
                only_in_fe = fe_set - be_set
                only_in_be = be_set - fe_set
                for fe_field in only_in_fe:
                    be_candidate = next(iter(only_in_be), "?")
                    be_loc = Location(file=exact.source_file, line=exact.line_number)
                    issues.append(
                        Issue(
                            issue_type="RESPONSE_FIELD_MISMATCH",
                            severity="medium",
                            frontend_location=fe_loc,
                            backend_location=be_loc,
                            expected=be_candidate,
                            actual=fe_field,
                            explanation=_fmt(
                                _EXPLANATIONS["RESPONSE_FIELD_MISMATCH"],
                                fe_field=fe_field,
                                be_field=be_candidate,
                            ),
                            suggested_fix=_fmt(
                                _FIXES["RESPONSE_FIELD_MISMATCH"],
                                fe_field=fe_field,
                                be_field=be_candidate,
                            ),
                        )
                    )

            # Check query parameter mismatches
            for fe_param in call.query_params:
                # Backend endpoint doesn't declare this param (simple check)
                issues.append(
                    Issue(
                        issue_type="QUERY_PARAM_MISMATCH",
                        severity="low",
                        frontend_location=fe_loc,
                        backend_location=Location(
                            file=exact.source_file, line=exact.line_number
                        ),
                        expected="(declared query param)",
                        actual=fe_param,
                        explanation=_fmt(
                            _EXPLANATIONS["QUERY_PARAM_MISMATCH"],
                            fe_param=fe_param,
                        ),
                        suggested_fix=_fmt(
                            _FIXES["QUERY_PARAM_MISMATCH"],
                            fe_param=fe_param,
                        ),
                    )
                )
            continue  # Exact match handled

        # 2. Same path, different method → METHOD_MISMATCH
        path_only = _find_endpoint_any_method(call, backend_endpoints)
        if path_only:
            be_loc = Location(file=path_only.source_file, line=path_only.line_number)
            issues.append(
                Issue(
                    issue_type="METHOD_MISMATCH",
                    severity="high",
                    frontend_location=fe_loc,
                    backend_location=be_loc,
                    expected=path_only.method,
                    actual=call.method,
                    explanation=_fmt(
                        _EXPLANATIONS["METHOD_MISMATCH"],
                        fe_method=call.method,
                        be_method=path_only.method,
                        path=call.path,
                    ),
                    suggested_fix=_fmt(
                        _FIXES["METHOD_MISMATCH"],
                        fe_method=call.method,
                        be_method=path_only.method,
                        fe_method_lower=call.method.lower(),
                        be_method_lower=path_only.method.lower(),
                        path=call.path,
                    ),
                )
            )
            continue

        # 3. No match at all → MISSING_BACKEND_ENDPOINT
        # (check if it looks like an internal path — skip absolute external URLs)
        if call.path.startswith("http://") or call.path.startswith("https://"):
            continue  # External URL, skip

        issues.append(
            Issue(
                issue_type="MISSING_BACKEND_ENDPOINT",
                severity="high",
                frontend_location=fe_loc,
                backend_location=None,
                expected=f"{call.method} {call.path}",
                actual="(not found)",
                explanation=_fmt(
                    _EXPLANATIONS["MISSING_BACKEND_ENDPOINT"],
                    method=call.method,
                    path=call.path,
                ),
                suggested_fix=_fmt(
                    _FIXES["MISSING_BACKEND_ENDPOINT"],
                    method=call.method,
                    path=call.path,
                ),
            )
        )

    return issues
