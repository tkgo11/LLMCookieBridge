"""Provider availability for LLMCookieBridge."""

from typing import NoReturn

__all__ = ["LLMCookieBridge", "ProviderUnavailableError", "available_providers"]


class ProviderUnavailableError(RuntimeError):
    """Raised when a provider has no live-verified integration."""


def available_providers() -> tuple[str, ...]:
    """Return the IDs of the providers enabled in this build."""
    return ()


class LLMCookieBridge:
    """Entry point for opening a live-verified provider integration."""

    @staticmethod
    def create(provider: str) -> NoReturn:
        """Reject provider creation while no integrations are enabled."""
        raise ProviderUnavailableError("This build has no live-verified providers.")
