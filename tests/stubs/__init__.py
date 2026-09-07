"""Deterministic stand-ins for the two external dependencies.

``llm`` replaces the Mistral HTTP provider, ``embedding`` replaces the
sentence-transformers model. Both are injected through
``app.dependency_overrides`` (see tests/conftest.py) so the whole service graph
below ``app/api/v1/deps.py`` receives them without any method patching.
"""
