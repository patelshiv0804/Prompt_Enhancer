"""
v1/auth.py — Thin re-export of auth module router.
"""

from app.modules.auth.router import router

__all__ = ["router"]
