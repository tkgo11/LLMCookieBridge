from __future__ import annotations

class BridgeError(Exception):
    """Base exception for llm-cookie-bridge."""


class AuthenticationError(BridgeError):
    """Raised when a provider cannot authenticate with the supplied cookies/session."""


class ProviderResponseError(BridgeError):
    """Raised when a provider returns a non-successful response."""

    def __init__(self, provider: str, status_code: int, message: str) -> None:
        super().__init__(f"{provider} returned HTTP {status_code}: {message}")
        self.provider = provider
        self.status_code = status_code
        self.message = message


class ParseError(BridgeError):
    """Raised when a provider response cannot be parsed."""


class RateLimitError(BridgeError):
    """Raised when a provider indicates a rate or usage limit."""
