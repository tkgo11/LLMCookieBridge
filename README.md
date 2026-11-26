# LLMCookieBridge

This development build has zero enabled providers. The 61 legacy adapters and
the cookie, token, chat, streaming, and refresh APIs were removed. See the
[provider verification record](docs/verification.md) for the observed blockers.

`available_providers()` returns an empty tuple. `LLMCookieBridge.create(provider)`
raises `ProviderUnavailableError` without opening a connection. The package
accepts no session credentials.

## Local checks

Use Python 3.11 or newer.

```sh
python -m pip install --upgrade 'setuptools>=84.1.0' '.[dev]'
python -m pytest
python -m ruff check
python -m ruff format --check
python -m mypy --strict src tests
python -m bandit -q -r src
python -m pip_audit --local --skip-editable
python -m build
python -m twine check --strict dist/*
```

[MIT license](LICENSE)
