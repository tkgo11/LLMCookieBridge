import pytest

from llm_cookie_bridge import (
    LLMCookieBridge,
    ProviderUnavailableError,
    available_providers,
)


def test_no_providers_are_enabled() -> None:
    assert available_providers() == ()


@pytest.mark.parametrize("provider", ["chatgpt", "duckai", "groq", "unknown"])
def test_create_rejects_provider_before_opening_a_session(provider: str) -> None:
    with pytest.raises(ProviderUnavailableError, match="no live-verified providers"):
        LLMCookieBridge.create(provider)


def test_error_does_not_echo_caller_input() -> None:
    with pytest.raises(ProviderUnavailableError) as error:
        LLMCookieBridge.create("private input")
    assert "private input" not in str(error.value)
