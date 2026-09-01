"""Provider adapter interfaces and shared errors."""

from .protocol import (
    AdapterError,
    AuthenticationError,
    MalformedResponseError,
    ProviderAdapter,
    ProviderResponseError,
)

__all__ = [
    "AdapterError",
    "AuthenticationError",
    "MalformedResponseError",
    "ProviderAdapter",
    "ProviderResponseError",
]
