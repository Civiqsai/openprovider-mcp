"""Openprovider API client — thin wrapper with automatic token lifecycle."""

import time
import httpx
from typing import Any

BASE_URL = "https://api.openprovider.eu/v1beta"

TOKEN_TTL = 48 * 3600          # 48 hours
REFRESH_MARGIN = 1 * 3600      # refresh 1 hour early


class OpenproviderClient:
    """HTTP client for the Openprovider REST API with automatic token management."""

    def __init__(self, username: str, password: str):
        self._username = username
        self._password = password
        self._token: str | None = None
        self._token_acquired: float = 0.0
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )

    def _token_expired(self) -> bool:
        if not self._token:
            return True
        return time.time() - self._token_acquired > (TOKEN_TTL - REFRESH_MARGIN)

    def _authenticate(self) -> None:
        resp = self._client.post(
            "/auth/login",
            json={"username": self._username, "password": self._password},
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code >= 400:
            try:
                body = resp.json()
            except Exception:
                body = {"error": resp.text}
            raise OpenproviderError(resp.status_code, body)
        data = resp.json()
        self._token = data["data"]["token"]
        self._token_acquired = time.time()

    def _ensure_token(self) -> str:
        if self._token_expired():
            self._authenticate()
        return self._token  # type: ignore[return-value]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._ensure_token()}",
            "Content-Type": "application/json",
        }

    def _handle_response(self, resp: httpx.Response) -> dict[str, Any]:
        if resp.status_code == 204:
            return {"success": True}
        if resp.status_code >= 400:
            try:
                body = resp.json()
            except Exception:
                body = {"error": resp.text}
            raise OpenproviderError(resp.status_code, body)
        return resp.json()

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        kwargs["headers"] = self._headers()
        resp = self._client.request(method, path, **kwargs)
        # On 401, re-authenticate once and retry
        if resp.status_code == 401:
            self._token = None
            kwargs["headers"] = self._headers()
            resp = self._client.request(method, path, **kwargs)
        return self._handle_response(resp)

    def get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        return self._request("GET", path, params=params)

    def post(self, path: str, json_data: dict | None = None) -> dict[str, Any]:
        return self._request("POST", path, json=json_data)

    def put(self, path: str, json_data: dict | None = None) -> dict[str, Any]:
        return self._request("PUT", path, json=json_data)

    def delete(self, path: str, params: dict | None = None) -> dict[str, Any]:
        return self._request("DELETE", path, params=params)


class OpenproviderError(Exception):
    def __init__(self, status_code: int, body: dict):
        self.status_code = status_code
        self.body = body
        # Openprovider errors: {"code": ..., "desc": ..., "data": ...}
        desc = body.get("desc", "")
        if not desc:
            desc = body.get("error", str(body))
        super().__init__(f"HTTP {status_code}: {desc}")
