"""
Intentionally removed (VULN-010).

This module previously defined ``AuthMiddleware``, a ``BaseHTTPMiddleware`` that
maintained its own ``PUBLIC_PATHS`` allowlist but performed **no** token
validation — its ``dispatch`` simply called ``call_next`` for every request.
It was never registered in ``app.main`` and gave a false sense of security
while silently letting all traffic through.

Authentication is enforced exclusively through FastAPI dependencies
(``app.core.security.get_current_user_id`` and ``app.api.v1.deps.get_current_user``),
which validate the JWT from the ``Authorization: Bearer`` header or the httpOnly
auth cookie on each protected route.

Do not reintroduce a pass-through auth middleware here. If global request
filtering is ever needed, implement real verification (and add tests) rather
than an allowlist that no-ops.
"""
