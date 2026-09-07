"""Test package for the PromptIQ backend.

Deliberately a real package (``__init__.py`` present) so that
``tests/unit/test_security.py`` and ``tests/integration/test_security.py`` can
coexist without pytest's basename collision, and so shared helpers are imported
as ``tests.factories`` / ``tests.stubs.llm`` rather than via sys.path magic.
"""
