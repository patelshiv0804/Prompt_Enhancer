"""Minimal ASGI scope/request builders for the unit tier.

Several things under test take a Starlette ``Request`` but touch only three
fields — ``request.client``, ``request.url.path`` and ``request.cookies``. Going
through ``httpx.AsyncClient`` to obtain one would drag in the whole application:
routing, middleware, dependency resolution and a database session. Building the
scope by hand keeps these tests honestly *unit*, and makes the inputs the code
actually reads visible at the call site.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from starlette.requests import Request

DEFAULT_CLIENT_IP = "203.0.113.10"  # TEST-NET-3, reserved for documentation
DEFAULT_PATH = "/api/v1/probe"


def make_scope(
    *,
    path: str = DEFAULT_PATH,
    client_ip: Optional[str] = DEFAULT_CLIENT_IP,
    headers: Optional[Mapping[str, str]] = None,
    cookies: Optional[Mapping[str, str]] = None,
    method: str = "GET",
    scope_type: str = "http",
) -> dict[str, Any]:
    """Build an ASGI scope. ``client_ip=None`` models a request with no client.

    That case is not hypothetical: it is what the rate limiters key as
    ``"unknown"``, and it happens behind proxies that strip the peer address.
    """
    raw_headers: list[tuple[bytes, bytes]] = [
        (name.lower().encode("latin-1"), value.encode("latin-1"))
        for name, value in (headers or {}).items()
    ]
    if cookies:
        jar = "; ".join(f"{name}={value}" for name, value in cookies.items())
        raw_headers.append((b"cookie", jar.encode("latin-1")))

    return {
        "type": scope_type,
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("latin-1"),
        "query_string": b"",
        "root_path": "",
        "headers": raw_headers,
        "client": (client_ip, 54321) if client_ip is not None else None,
        "server": ("testserver", 80),
    }


def make_request(**kwargs: Any) -> Request:
    return Request(make_scope(**kwargs))


class RecordingApp:
    """Innermost ASGI app: counts how many requests reached it."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def __call__(self, scope, receive, send) -> None:  # noqa: ANN001
        self.calls.append(scope.get("path", ""))
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})


class SendRecorder:
    """Collects the ASGI messages a middleware emits."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def __call__(self, message: dict[str, Any]) -> None:
        self.messages.append(message)

    @property
    def status(self) -> Optional[int]:
        for message in self.messages:
            if message["type"] == "http.response.start":
                return message["status"]
        return None

    @property
    def body(self) -> bytes:
        return b"".join(
            message.get("body", b"")
            for message in self.messages
            if message["type"] == "http.response.body"
        )

    def header(self, name: str) -> Optional[bytes]:
        wanted = name.lower().encode("latin-1")
        for message in self.messages:
            if message["type"] == "http.response.start":
                for key, value in message.get("headers", []):
                    if key.lower() == wanted:
                        return value
        return None


async def noop_receive() -> dict[str, Any]:
    return {"type": "http.request", "body": b"", "more_body": False}


class FakeClock:
    """Stand-in for the ``time`` module inside a limiter.

    Patched over the module-global ``time`` name rather than over
    ``time.monotonic`` itself: the real ``time.monotonic`` also drives the
    asyncio event loop's timers, and replacing it globally makes the loop
    misbehave in ways that surface as unrelated failures.
    """

    def __init__(self, start: float = 1_000.0) -> None:
        self.now = start

    def monotonic(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds
