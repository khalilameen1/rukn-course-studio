"""Credit/network safety — tests must never hit real providers or the network."""

from __future__ import annotations

import socket
from typing import Any

_NETWORK_BLOCKED = False
_ORIGINAL_SOCKET = socket.socket
_REAL_PROVIDER_CALLS = 0


class NetworkBlockedError(RuntimeError):
    """Raised when code under test attempts network I/O."""


class RealProviderBlockedError(RuntimeError):
    """Raised when a non-fake AI provider is constructed/used in guarded tests."""


def block_network() -> None:
    global _NETWORK_BLOCKED
    _NETWORK_BLOCKED = True

    class GuardedSocket(_ORIGINAL_SOCKET):  # type: ignore[misc,valid-type]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise NetworkBlockedError(
                "Network access blocked in quality tests — use FakeProvider/fixtures only"
            )

    socket.socket = GuardedSocket  # type: ignore[misc,assignment]


def unblock_network() -> None:
    global _NETWORK_BLOCKED
    _NETWORK_BLOCKED = False
    socket.socket = _ORIGINAL_SOCKET  # type: ignore[misc,assignment]


def record_real_provider_attempt(provider_name: str) -> None:
    global _REAL_PROVIDER_CALLS
    name = (provider_name or "").strip().lower()
    if name and name != "fake":
        _REAL_PROVIDER_CALLS += 1
        raise RealProviderBlockedError(
            f"Real provider '{provider_name}' blocked in credit-safe tests"
        )


def real_provider_call_count() -> int:
    return _REAL_PROVIDER_CALLS


def reset_real_provider_call_count() -> None:
    global _REAL_PROVIDER_CALLS
    _REAL_PROVIDER_CALLS = 0


def assert_credit_safe(*, provider_name: str | None = None) -> None:
    if provider_name and provider_name.strip().lower() not in {"", "fake"}:
        raise RealProviderBlockedError(
            f"Provider must be fake in credit-safe mode, got {provider_name}"
        )
    if _REAL_PROVIDER_CALLS != 0:
        raise RealProviderBlockedError(
            f"Real provider calls observed: {_REAL_PROVIDER_CALLS}"
        )
