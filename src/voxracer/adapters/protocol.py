"""Typed boundary between provider integrations and the core package."""

from __future__ import annotations

from typing import NewType, Protocol, runtime_checkable

from ..model import Session

CallId = NewType("CallId", str)


class AdapterError(RuntimeError):
    """Base error for an adapter operation."""


class AuthenticationError(AdapterError):
    """The provider rejected the supplied credential."""


class ProviderResponseError(AdapterError):
    """The provider returned an error response."""


class MalformedResponseError(AdapterError):
    """The provider response does not have the required shape."""


@runtime_checkable
class ProviderAdapter(Protocol):
    """Read-only provider integration used by the application layer."""

    name: str

    def list_call_ids(self, credential: str, *, limit: int = 30) -> list[CallId]:
        """Return recent call identifiers, newest first."""

    def fetch_session(self, credential: str, call_id: CallId) -> Session:
        """Fetch and map one call to the canonical session model."""
