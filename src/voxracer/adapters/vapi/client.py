"""Small read-only Vapi HTTP client."""

from __future__ import annotations

import gzip
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, cast

from ..protocol import AuthenticationError, MalformedResponseError, ProviderResponseError

API_BASE = "https://api.vapi.ai"
MAX_RESPONSE_BYTES = 10 * 1024 * 1024
USER_AGENT = "voxracer/0.1.0a1"


class VapiClient:
    """Fetch call records needed by the adapter."""

    def __init__(self, api_key: str, *, opener: Any = urllib.request.urlopen) -> None:
        self._api_key = api_key
        self._opener = opener

    def _get_json(self, path: str) -> Any:
        try:
            return json.loads(self._get_bytes(f"{API_BASE}{path}"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MalformedResponseError("Vapi returned invalid JSON") from exc

    def _get_bytes(self, url: str, *, authenticated: bool = True) -> bytes:
        headers = {"User-Agent": USER_AGENT}
        if authenticated:
            headers["Authorization"] = f"Bearer {self._api_key}"
        request = urllib.request.Request(
            url,
            headers=headers,
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
        return cast(bytes, payload)

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

    def fetch_event_log(self, raw: dict[str, Any]) -> list[dict[str, Any]]:
        artifact = raw.get("artifact")
        url = artifact.get("presignedLogUrl") if isinstance(artifact, dict) else None
        if not isinstance(url, str) or not url:
            return []
        try:
            payload = gzip.decompress(self._get_bytes(url, authenticated=False)).decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise MalformedResponseError("Vapi event log is not valid gzip JSONL") from exc
        events: list[dict[str, Any]] = []
        for line in payload.splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise MalformedResponseError("Vapi event log contains invalid JSON") from exc
            if not isinstance(value, dict) or not isinstance(value.get("attributes"), dict):
                continue
            attributes = value["attributes"]
            events.append({
                "time": value.get("time"),
                "attributes": {
                    key: attributes[key]
                    for key in (
                        "event", "turnId", "spanId", "latency", "duration"
                    )
                    if key in attributes
                },
            })
        return events
