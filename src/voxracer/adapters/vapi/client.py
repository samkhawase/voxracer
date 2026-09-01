"""Small read-only Vapi HTTP client."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ..protocol import AuthenticationError, MalformedResponseError, ProviderResponseError

API_BASE = "https://api.vapi.ai"
MAX_RESPONSE_BYTES = 10 * 1024 * 1024


class VapiClient:
    """Fetch call records needed by the adapter."""

    def __init__(self, api_key: str, *, opener: Any = urllib.request.urlopen) -> None:
        self._api_key = api_key
        self._opener = opener

    def _get_json(self, path: str) -> Any:
        request = urllib.request.Request(
            f"{API_BASE}{path}",
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        try:
            with self._opener(request, timeout=30) as response:
                payload = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise AuthenticationError("Vapi rejected the API key") from None
            raise ProviderResponseError(f"Vapi returned HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderResponseError(f"Vapi request failed: {exc}") from None
        if len(payload) > MAX_RESPONSE_BYTES:
            raise ProviderResponseError("Vapi response is too large")
        try:
            return json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MalformedResponseError("Vapi returned invalid JSON") from exc

    def list_call_ids(self, *, limit: int = 30) -> list[str]:
        data = self._get_json(f"/call?limit={limit}")
        if not isinstance(data, list):
            raise MalformedResponseError("Vapi response has no call list")
        return [item["id"] for item in data if isinstance(item, dict) and isinstance(item.get("id"), str)]

    def fetch_call(self, call_id: str) -> dict[str, Any]:
        encoded_id = urllib.parse.quote(call_id, safe="")
        data = self._get_json(f"/call/{encoded_id}")
        if not isinstance(data, dict):
            raise MalformedResponseError("Vapi call response is not an object")
        return data
