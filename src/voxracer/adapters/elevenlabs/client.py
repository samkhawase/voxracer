"""Small read-only ElevenLabs HTTP client."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ..protocol import AuthenticationError, MalformedResponseError, ProviderResponseError

API_BASE = "https://api.elevenlabs.io"
MAX_RESPONSE_BYTES = 10 * 1024 * 1024


class ElevenLabsClient:
    """Fetch only the provider records needed by the adapter."""

    def __init__(self, api_key: str, *, opener: Any = urllib.request.urlopen) -> None:
        self._api_key = api_key
        self._opener = opener

    def _get_json(self, path: str, query: str = "") -> dict[str, Any]:
        url = f"{API_BASE}{path}{query}"
        request = urllib.request.Request(url, headers={"xi-api-key": self._api_key})
        try:
            with self._opener(request, timeout=30) as response:
                payload = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise AuthenticationError("ElevenLabs rejected the API key") from None
            raise ProviderResponseError(f"ElevenLabs returned HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderResponseError(f"ElevenLabs request failed: {exc.reason if hasattr(exc, 'reason') else exc}") from None
        if len(payload) > MAX_RESPONSE_BYTES:
            raise ProviderResponseError("ElevenLabs response is too large")
        try:
            data = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MalformedResponseError("ElevenLabs returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise MalformedResponseError("ElevenLabs returned a JSON value, not an object")
        return data

    def list_conversation_ids(self, *, limit: int = 30) -> list[str]:
        data = self._get_json("/v1/convai/conversations", f"?page_size={limit}")
        conversations = data.get("conversations")
        if not isinstance(conversations, list):
            raise MalformedResponseError("ElevenLabs response has no conversation list")
        ids = [item.get("conversation_id") for item in conversations if isinstance(item, dict)]
        return [conversation_id for conversation_id in ids if isinstance(conversation_id, str)]

    def fetch_otlp(self, conversation_id: str) -> dict[str, Any]:
        encoded_id = urllib.parse.quote(conversation_id, safe="")
        return self._get_json(
            f"/v1/convai/conversations/{encoded_id}",
            "?format=opentelemetry",
        )

    def fetch_transcript(self, conversation_id: str) -> dict[str, Any]:
        encoded_id = urllib.parse.quote(conversation_id, safe="")
        return self._get_json(f"/v1/convai/conversations/{encoded_id}")
