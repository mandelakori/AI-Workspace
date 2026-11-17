from __future__ import annotations

import json
from collections.abc import Callable
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HTTPFailure(RuntimeError):
    def __init__(self, status: int, error_code: str = ""):
        super().__init__(f"HTTP {status}" + (f" ({error_code})" if error_code else ""))
        self.status = status
        self.error_code = error_code


def request(url: str, method: str = "GET", body: dict | None = None,
            key: str = "", timeout: float = 5, *,
            capture: Callable[[str, bytes], None] | None = None) -> dict:
    headers = {"Accept": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = None
    if body is not None:
        payload = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = Request(url, data=payload, method=method, headers=headers)
    if capture and req.data is not None:
        capture("request", req.data)
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(req, timeout=timeout) as response:
            content = response.read(2_097_153)
    except HTTPError as exc:
        with exc:
            content = exc.read(2_097_153 if capture else 4096)
            if capture:
                capture("response", content)
            try:
                code = json.loads(content).get("error", {}).get("code", "")
            except (ValueError, AttributeError):
                code = ""
        raise HTTPFailure(exc.code, str(code)[:80]) from None
    if capture:
        capture("response", content)
    if len(content) > 2_097_152:
        raise ValueError("response exceeds 2 MiB")
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    return data
