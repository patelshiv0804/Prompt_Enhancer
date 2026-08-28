"""Unit tier: no database, no network, no filesystem.

Every module here is imported by ``tests/unit/...`` paths, so this package must
exist for pytest to distinguish ``tests/unit/test_security.py`` from any
same-named module in another tier.
"""
