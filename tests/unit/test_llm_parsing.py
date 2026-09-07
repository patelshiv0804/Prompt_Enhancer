"""Unit tests for app/services/llm/mistral_provider.py.

``app/services/llm/schemas.py`` holds plain dataclasses with no parsing logic, so
the response-parsing behaviour the plan calls for lives here instead: the four
``_parse*``/``_first_choice``/``_extract_delta`` helpers, the error mapping in
``_post``, and the SSE loop in ``optimize_prompt_stream``.

No network. ``get_shared_client`` is replaced with a fake whose responses are real
``httpx.Response`` objects, so ``raise_for_status`` and ``.json()`` behave exactly
as they do against the live API.

WHY THE IMPORT-TIME CAPTURES BELOW
---------------------------------
``tests/conftest.py`` installs an autouse fixture that points the five public
provider methods at ``StubLLMProvider`` — that is what keeps the rest of the suite
off the network. It replaces the attributes on the class, so the original function
objects are still reachable if they are captured at import time, before any test
runs. That is the only way to exercise the real methods; without it this code
would have no coverage at any tier.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import httpx
import pytest

from app.core.config import settings
from app.services.llm import mistral_provider as mistral_module
from app.services.llm.exceptions import (
    LLMProviderError,
    LLMRequestError,
    LLMTimeoutError,
)
from app.services.llm.mistral_provider import MistralProvider, close_shared_client

pytestmark = pytest.mark.unit

ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
PROVIDER_NAME = "groq"

# Captured before conftest's autouse patch can replace them. See module docstring.
REAL_ANALYZE = MistralProvider.analyze_prompt
REAL_OPTIMIZE = MistralProvider.optimize_prompt
REAL_STREAM = MistralProvider.optimize_prompt_stream
REAL_GENERATE = MistralProvider.generate
REAL_HEALTH_CHECK = MistralProvider.health_check


def completion(content: str, **extra: Any) -> dict[str, Any]:
    """A minimal Mistral chat-completion body."""
    return {"choices": [{"message": {"role": "assistant", "content": content}, **extra}]}


def bare_provider() -> MistralProvider:
    """A provider with the attributes ``__init__`` sets, but without running it.

    ``__init__`` raises unless ``settings.llm_api_key`` is populated, and the
    conftest replaces it anyway; building the instance directly keeps these tests
    independent of both.
    """
    provider = object.__new__(MistralProvider)
    provider.api_key = "unit-test-key"
    provider.model = "unit-test-model"
    provider.timeout = 5.0
    provider.temperature = 0.3
    provider.max_tokens = 128
    provider.provider_name = PROVIDER_NAME
    provider.endpoint = ENDPOINT
    provider.headers = {
        "Authorization": "Bearer unit-test-key",
        "Content-Type": "application/json",
    }
    return provider


@pytest.fixture
def provider() -> MistralProvider:
    return bare_provider()


# ─────────────────────────────────────────────────────────────────────────────
# Fake transport
# ─────────────────────────────────────────────────────────────────────────────


def response(status_code: int = 200, **kwargs: Any) -> httpx.Response:
    return httpx.Response(
        status_code, request=httpx.Request("POST", ENDPOINT), **kwargs
    )


class FakeHTTPClient:
    """Stands in for the shared ``httpx.AsyncClient``.

    Records what was sent so the payload assertions do not need a second mechanism.
    """

    def __init__(
        self,
        *,
        result: Optional[httpx.Response] = None,
        error: Optional[BaseException] = None,
        stream_lines: Optional[list[str]] = None,
        stream_status: int = 200,
        stream_error: Optional[BaseException] = None,
    ) -> None:
        self.result = result
        self.error = error
        self.stream_lines = stream_lines or []
        self.stream_status = stream_status
        self.stream_error = stream_error
        self.posts: list[dict[str, Any]] = []
        self.streams: list[dict[str, Any]] = []
        self.last_stream_response: Optional[_FakeStreamResponse] = None
        self.is_closed = False

    async def post(self, url, json=None, headers=None):
        self.posts.append({"url": url, "json": json, "headers": headers})
        if self.error is not None:
            raise self.error
        return self.result

    def stream(self, method, url, json=None, headers=None):
        self.streams.append(
            {"method": method, "url": url, "json": json, "headers": headers}
        )
        self.last_stream_response = _FakeStreamResponse(
            self.stream_lines, self.stream_status, self.stream_error
        )
        return _FakeStreamContext(self.last_stream_response)


class _FakeStreamResponse:
    def __init__(
        self, lines: list[str], status_code: int, error: Optional[BaseException]
    ) -> None:
        self.lines = lines
        self.status_code = status_code
        self.error = error
        self.read_before_raise = False

    async def aiter_lines(self):
        if self.error is not None:
            raise self.error
        for line in self.lines:
            yield line

    async def aread(self) -> bytes:
        self.read_before_raise = True
        return b'{"message": "error detail"}'

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("POST", ENDPOINT)
            raise httpx.HTTPStatusError(
                "error",
                request=request,
                response=httpx.Response(self.status_code, request=request),
            )


class _FakeStreamContext:
    def __init__(self, resp: _FakeStreamResponse) -> None:
        self.resp = resp

    async def __aenter__(self) -> _FakeStreamResponse:
        return self.resp

    async def __aexit__(self, *_exc) -> bool:
        return False


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch):
    """Install a fake shared client and hand the test a way to configure it."""
    holder: dict[str, FakeHTTPClient] = {}

    def install(**kwargs: Any) -> FakeHTTPClient:
        client = FakeHTTPClient(**kwargs)
        holder["client"] = client

        async def fake_get_shared_client() -> FakeHTTPClient:
            return client

        monkeypatch.setattr(mistral_module, "get_shared_client", fake_get_shared_client)
        return client

    return install


async def collect(stream) -> list[str]:
    return [chunk async for chunk in stream]


# ─────────────────────────────────────────────────────────────────────────────
# _first_choice
# ─────────────────────────────────────────────────────────────────────────────


def test_first_choice_returns_the_leading_choice(provider: MistralProvider) -> None:
    data = {"choices": [{"index": 0}, {"index": 1}]}

    assert provider._first_choice(data) == {"index": 0}


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"choices": None},
        {"choices": []},
        {"choices": {}},
        {"choices": "not-a-list"},
        {"choices": ["a string, not an object"]},
        {"choices": [None]},
    ],
    ids=[
        "no-choices",
        "null-choices",
        "empty-choices",
        "dict-choices",
        "string-choices",
        "string-item",
        "null-item",
    ],
)
def test_first_choice_returns_none_for_every_wrong_shape(
    provider: MistralProvider, data: dict
) -> None:
    assert provider._first_choice(data) is None


# ─────────────────────────────────────────────────────────────────────────────
# _parse_text
# ─────────────────────────────────────────────────────────────────────────────


def test_parse_text_extracts_the_message_content(provider: MistralProvider) -> None:
    assert provider._parse_text(completion("the answer")) == "the answer"


def test_parse_text_does_not_strip(provider: MistralProvider) -> None:
    """Callers strip; the parser must not, or streamed and blocking output would
    disagree about leading whitespace."""
    assert provider._parse_text(completion("  padded  ")) == "  padded  "


def test_parse_text_coerces_non_string_content(provider: MistralProvider) -> None:
    """``str(...)`` around the content, so a numeric payload does not raise."""
    assert provider._parse_text(completion(123)) == "123"  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "data",
    [None, [], "a string", 42],
    ids=["none", "list", "string", "int"],
)
def test_parse_text_rejects_a_non_dict_body(provider: MistralProvider, data: Any) -> None:
    """The isinstance guard is what keeps ``"choices" in data`` from doing a
    substring or membership test on the wrong type."""
    with pytest.raises(LLMProviderError, match="Unexpected LLM response format"):
        provider._parse_text(data)


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"choices": []},
        {"choices": [{}]},
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"role": "assistant"}}]},
        {"choices": [{"text": "legacy completion format"}]},
        {"error": {"message": "invalid api key"}},
    ],
    ids=[
        "empty-body",
        "empty-choices",
        "choice-without-message",
        "message-without-content",
        "message-with-role-only",
        "legacy-text-field",
        "error-body",
    ],
)
def test_parse_text_rejects_a_dict_it_cannot_read(
    provider: MistralProvider, data: dict
) -> None:
    with pytest.raises(LLMProviderError, match="Unable to parse LLM response"):
        provider._parse_text(data)


def test_parse_text_accepts_a_null_content(provider: MistralProvider) -> None:
    """``"content" in message`` is a key check, not a truthiness check.

    Mistral returns ``content: null`` when a response is cut off by a content
    filter, and this turns into the string ``"None"`` rather than an error. Pinned
    because a downstream ``"None"`` prompt is a confusing symptom to trace back.
    """
    assert provider._parse_text(completion(None)) == "None"  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────────
# _extract_delta — the streaming hot path
# ─────────────────────────────────────────────────────────────────────────────


def test_extract_delta_returns_the_content_fragment(provider: MistralProvider) -> None:
    chunk = {"choices": [{"delta": {"content": "Act"}}]}

    assert provider._extract_delta(chunk) == "Act"


@pytest.mark.parametrize(
    "chunk",
    [
        {},
        {"choices": []},
        {"choices": [{}]},
        {"choices": [{"delta": None}]},
        {"choices": [{"delta": {}}]},
        {"choices": [{"delta": {"role": "assistant"}}]},
        {"choices": [{"delta": {"content": None}}]},
        {"choices": [{"delta": {"content": 5}}]},
        {"choices": [{"message": {"content": "not a delta"}}]},
        {"choices": [{"finish_reason": "stop", "delta": {}}]},
    ],
    ids=[
        "empty",
        "no-choices",
        "no-delta",
        "null-delta",
        "empty-delta",
        "role-only",
        "null-content",
        "int-content",
        "message-instead-of-delta",
        "terminal-chunk",
    ],
)
def test_extract_delta_returns_empty_string_for_anything_unexpected(
    provider: MistralProvider, chunk: dict
) -> None:
    """Every mismatch collapses to ``""``, which the caller then skips.

    The final chunk of a real stream carries ``finish_reason`` and an empty delta,
    so this path runs on every successful request — it is the normal case, not the
    exceptional one.
    """
    assert provider._extract_delta(chunk) == ""


@pytest.mark.parametrize("chunk", [5, None, True], ids=["int", "none", "bool"])
def test_extract_delta_raises_on_a_non_container_chunk(
    provider: MistralProvider, chunk: Any
) -> None:
    """Documented gap, pinning current behaviour.

    ``_first_choice`` starts with ``"choices" in data``, which raises TypeError
    when ``data`` is not a container — and ``_extract_delta``, unlike
    ``_parse_text``, has no isinstance guard in front of it. A stream line such as
    ``data: 5`` parses as valid JSON, so it reaches here and aborts the whole
    stream (``optimize_prompt_stream`` converts it to ``LLMProviderError``), even
    though a line of *invalid* JSON is deliberately skipped a few lines earlier.

    Not reachable from Mistral's real output, so this is a robustness gap rather
    than a live bug — but the asymmetry with the JSONDecodeError branch is worth
    recording.
    """
    with pytest.raises(TypeError):
        provider._extract_delta(chunk)


# ─────────────────────────────────────────────────────────────────────────────
# _parse_analysis
# ─────────────────────────────────────────────────────────────────────────────


def test_parse_analysis_is_a_hardcoded_placeholder(provider: MistralProvider) -> None:
    """KNOWN DEFECT — pinning current behaviour.

    ``_parse_analysis`` ignores the model's response entirely: it returns zeros for
    all five dimensions, an unconditional ``grade="B"``, and stashes the raw text
    in ``strengths``. So ``MistralProvider.analyze_prompt`` reports a B with no
    scores no matter what was analysed.

    The route users actually hit is ``PromptAnalysisService``, which does its own
    JSON parsing and scoring (see tests/unit/test_prompt_analysis_service.py), so
    this only affects callers of the provider method directly. Invert this test if
    real parsing is added.
    """
    result = provider._parse_analysis("clarity is poor; grade: F")

    assert (
        result.clarity,
        result.context,
        result.specificity,
        result.constraints,
        result.output_structure,
    ) == (0.0, 0.0, 0.0, 0.0, 0.0)
    assert result.grade == "B"
    assert result.strengths == "clarity is poor; grade: F"
    assert result.weaknesses == ""
    assert result.recommendations == ""


# ─────────────────────────────────────────────────────────────────────────────
# _post — transport error mapping
# ─────────────────────────────────────────────────────────────────────────────


async def test_post_returns_the_decoded_body(
    provider: MistralProvider, transport
) -> None:
    client = transport(result=response(200, json=completion("ok")))

    assert await provider._post({"model": "m"}) == completion("ok")
    assert client.posts[0]["url"] == ENDPOINT
    assert client.posts[0]["headers"] == provider.headers
    assert client.posts[0]["json"] == {"model": "m"}


async def test_post_maps_a_read_timeout(provider: MistralProvider, transport) -> None:
    """The retry loop in ``PromptEnhancementService`` catches ``LLMTimeoutError``
    specifically, so this mapping is what makes a slow Mistral retryable."""
    transport(error=httpx.ReadTimeout("too slow"))

    with pytest.raises(LLMTimeoutError, match="groq request timed out"):
        await provider._post({})


@pytest.mark.parametrize("status", [400, 401, 429, 500, 503])
async def test_post_maps_every_http_error_status(
    provider: MistralProvider, transport, status: int
) -> None:
    """Also retried by the enhancement service, via ``LLMRequestError``.

    Note the flattening: a 401 (bad API key, never going to succeed) is
    indistinguishable from a 503 (transient), so both get retried three times.
    """
    transport(result=response(status, json={"message": "nope"}))

    with pytest.raises(LLMRequestError, match="groq request failed"):
        await provider._post({})


@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectError("no route to host"),
        httpx.ConnectTimeout("handshake stalled"),
        httpx.RemoteProtocolError("server disconnected"),
        RuntimeError("something else entirely"),
    ],
    ids=["connect-error", "connect-timeout", "protocol-error", "non-httpx"],
)
async def test_post_maps_everything_else_to_a_provider_error(
    provider: MistralProvider, transport, error: Exception
) -> None:
    """``ConnectTimeout`` lands here rather than in the timeout branch.

    Only ``ReadTimeout`` is special-cased, so a connect-phase timeout raises
    ``LLMProviderError`` and is *not* retried. Worth knowing when reading a
    production trace.
    """
    transport(error=error)

    with pytest.raises(LLMProviderError, match="Unexpected groq provider error"):
        await provider._post({})


async def test_post_maps_an_undecodable_body_to_a_provider_error(
    provider: MistralProvider, transport
) -> None:
    transport(result=response(200, text="<html>gateway error</html>"))

    with pytest.raises(LLMProviderError, match="Unexpected groq provider error"):
        await provider._post({})


# ─────────────────────────────────────────────────────────────────────────────
# The public blocking methods
# ─────────────────────────────────────────────────────────────────────────────


async def test_optimize_prompt_returns_stripped_text_and_metadata(
    provider: MistralProvider, transport
) -> None:
    body = completion("  Act as a senior editor.  ", finish_reason="stop")
    body["usage"] = {"prompt_tokens": 11, "completion_tokens": 22}
    client = transport(result=response(200, json=body))

    result = await REAL_OPTIMIZE(provider, "raw prompt", "template-123", max_tokens=4096)

    assert result.optimized_prompt == "Act as a senior editor."
    assert result.template_id == "template-123"
    assert result.score is None
    assert result.metadata == {
        "provider": PROVIDER_NAME,
        "finish_reason": "stop",
        "usage": {"prompt_tokens": 11, "completion_tokens": 22},
        "max_tokens": 4096,
    }
    assert client.posts[0]["json"]["max_tokens"] == 4096
    assert client.posts[0]["json"]["messages"] == [
        {"role": "user", "content": "raw prompt"}
    ]


async def test_optimize_prompt_falls_back_to_the_instance_defaults(
    provider: MistralProvider, transport
) -> None:
    client = transport(result=response(200, json=completion("out")))

    await REAL_OPTIMIZE(provider, "raw prompt", "template-123")

    payload = client.posts[0]["json"]
    assert payload["max_tokens"] == provider.max_tokens
    assert payload["temperature"] == provider.temperature
    assert payload["model"] == provider.model


async def test_optimize_prompt_tolerates_a_missing_finish_reason_and_usage(
    provider: MistralProvider, transport
) -> None:
    transport(result=response(200, json=completion("out")))

    result = await REAL_OPTIMIZE(provider, "p", "t")

    assert result.metadata["finish_reason"] is None
    assert result.metadata["usage"] is None


async def test_generate_returns_stripped_text(
    provider: MistralProvider, transport
) -> None:
    transport(result=response(200, json=completion("\n  generated  \n")))

    result = await REAL_GENERATE(provider, "a prompt")

    assert result.text == "generated"
    assert result.metadata == {"provider": PROVIDER_NAME}


async def test_generate_defaults_to_256_tokens(
    provider: MistralProvider, transport
) -> None:
    """Deliberately independent of ``self.max_tokens`` — ``generate`` backs the
    short classification and intent calls, not prompt optimisation."""
    client = transport(result=response(200, json=completion("x")))

    await REAL_GENERATE(provider, "a prompt")

    assert client.posts[0]["json"]["max_tokens"] == 256
    assert client.posts[0]["json"]["temperature"] == 0.7


async def test_analyze_prompt_sends_the_prompt_and_returns_the_placeholder(
    provider: MistralProvider, transport
) -> None:
    client = transport(result=response(200, json=completion("some analysis prose")))

    result = await REAL_ANALYZE(provider, "my prompt text")

    assert "my prompt text" in client.posts[0]["json"]["messages"][0]["content"]
    assert result.strengths == "some analysis prose"
    assert result.grade == "B"


async def test_health_check_is_healthy_on_a_successful_call(
    provider: MistralProvider, transport
) -> None:
    client = transport(result=response(200, json=completion("ok")))

    result = await REAL_HEALTH_CHECK(provider)

    assert result.healthy is True
    assert result.details is None
    assert client.posts[0]["json"]["max_tokens"] == 1


async def test_health_check_reports_failure_instead_of_raising(
    provider: MistralProvider, transport
) -> None:
    """``/health`` must stay answerable when Mistral is down, so every ``LLMError``
    is converted into a payload rather than propagated."""
    transport(error=httpx.ReadTimeout("down"))

    result = await REAL_HEALTH_CHECK(provider)

    assert result.healthy is False
    assert "timed out" in result.details


async def test_health_check_does_not_swallow_a_non_llm_error(
    provider: MistralProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only ``LLMError`` is caught. A programming error still surfaces."""

    async def broken(_self, _payload):
        raise KeyError("a bug, not an outage")

    monkeypatch.setattr(MistralProvider, "_post", broken)

    with pytest.raises(KeyError):
        await REAL_HEALTH_CHECK(provider)


# ─────────────────────────────────────────────────────────────────────────────
# optimize_prompt_stream — SSE framing
# ─────────────────────────────────────────────────────────────────────────────


def sse(chunk: dict) -> str:
    return f"data: {json.dumps(chunk)}"


def delta(content: str) -> str:
    return sse({"choices": [{"delta": {"content": content}}]})


async def test_stream_yields_only_content_deltas(
    provider: MistralProvider, transport
) -> None:
    transport(
        stream_lines=[
            delta("Act"),
            delta(" as"),
            delta(" an editor."),
            sse({"choices": [{"delta": {}, "finish_reason": "stop"}]}),
            "data: [DONE]",
        ]
    )

    assert await collect(REAL_STREAM(provider, "p")) == ["Act", " as", " an editor."]


async def test_stream_requests_streaming_mode(
    provider: MistralProvider, transport
) -> None:
    client = transport(stream_lines=["data: [DONE]"])

    await collect(REAL_STREAM(provider, "p", max_tokens=99))

    (call,) = client.streams
    assert call["method"] == "POST"
    assert call["url"] == ENDPOINT
    assert call["json"]["stream"] is True
    assert call["json"]["max_tokens"] == 99


async def test_stream_ignores_framing_and_keep_alive_lines(
    provider: MistralProvider, transport
) -> None:
    """Blank lines separate SSE frames, ``:`` lines are comments used as
    keep-alives, and ``event:``/``id:`` lines are metadata. None carry content."""
    transport(
        stream_lines=[
            "",
            ": keep-alive",
            "event: message",
            "id: 42",
            "retry: 1000",
            delta("hello"),
            "",
            "data: [DONE]",
        ]
    )

    assert await collect(REAL_STREAM(provider, "p")) == ["hello"]


async def test_stream_skips_lines_that_are_not_valid_json(
    provider: MistralProvider, transport
) -> None:
    transport(
        stream_lines=[
            "data: {not valid json",
            "data: ",
            delta("survived"),
            "data: [DONE]",
        ]
    )

    assert await collect(REAL_STREAM(provider, "p")) == ["survived"]


async def test_stream_stops_at_the_done_sentinel(
    provider: MistralProvider, transport
) -> None:
    """Anything after ``[DONE]`` is not part of the response and must be dropped."""
    transport(
        stream_lines=[delta("kept"), "data: [DONE]", delta("must not be yielded")]
    )

    assert await collect(REAL_STREAM(provider, "p")) == ["kept"]


async def test_stream_drops_empty_deltas(provider: MistralProvider, transport) -> None:
    """``if delta:`` — an empty fragment would otherwise emit a contentless SSE
    frame to the browser for every terminal chunk."""
    transport(stream_lines=[delta(""), delta("real"), delta(""), "data: [DONE]"])

    assert await collect(REAL_STREAM(provider, "p")) == ["real"]


async def test_stream_tolerates_a_missing_done_sentinel(
    provider: MistralProvider, transport
) -> None:
    """A truncated stream ends the iteration rather than hanging or raising."""
    transport(stream_lines=[delta("a"), delta("b")])

    assert await collect(REAL_STREAM(provider, "p")) == ["a", "b"]


async def test_stream_accepts_a_data_line_without_a_space(
    provider: MistralProvider, transport
) -> None:
    """``line[len("data:"):].strip()`` — the space after the colon is optional in
    the SSE spec and Mistral's framing is not guaranteed to include it."""
    transport(stream_lines=['data:{"choices":[{"delta":{"content":"tight"}}]}'])

    assert await collect(REAL_STREAM(provider, "p")) == ["tight"]


async def test_stream_maps_an_http_error_status(
    provider: MistralProvider, transport
) -> None:
    """The body is drained before ``raise_for_status`` so the API's error detail
    reaches the log — httpx will not read a streamed body on its own."""
    client = transport(stream_status=429, stream_lines=[delta("never reached")])

    with pytest.raises(LLMRequestError, match="groq streaming request failed"):
        await collect(REAL_STREAM(provider, "p"))

    assert client.last_stream_response.read_before_raise is True


async def test_stream_maps_a_read_timeout(provider: MistralProvider, transport) -> None:
    transport(stream_error=httpx.ReadTimeout("stalled mid-stream"))

    with pytest.raises(LLMTimeoutError, match="groq streaming request timed out"):
        await collect(REAL_STREAM(provider, "p"))


async def test_stream_reraises_an_llm_error_unwrapped(
    provider: MistralProvider, transport
) -> None:
    """``except LLMError: raise`` sits above the catch-all, so an error that is
    already classified keeps its type instead of being flattened to
    ``LLMProviderError``."""
    transport(stream_error=LLMRequestError("already classified"))

    with pytest.raises(LLMRequestError, match="already classified"):
        await collect(REAL_STREAM(provider, "p"))


async def test_stream_maps_anything_else_to_a_provider_error(
    provider: MistralProvider, transport
) -> None:
    transport(stream_error=httpx.ConnectError("no route"))

    with pytest.raises(LLMProviderError, match="Unexpected groq provider streaming"):
        await collect(REAL_STREAM(provider, "p"))


# ─────────────────────────────────────────────────────────────────────────────
# The process-wide shared client
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
async def isolated_shared_client():
    """Save, clear and restore the module globals around a test.

    ``_shared_client`` is process-wide by design, so a test that creates one would
    otherwise leave a live client (and an unclosed-transport warning) behind for
    the rest of the session.
    """
    saved_client = mistral_module._shared_client
    saved_lock = mistral_module._client_lock
    mistral_module._shared_client = None
    try:
        yield
    finally:
        await close_shared_client()
        mistral_module._shared_client = saved_client
        mistral_module._client_lock = saved_lock


async def test_the_shared_client_is_created_once_and_reused(
    isolated_shared_client,
) -> None:
    """The reason it exists: one TLS handshake per process instead of per request."""
    first = await mistral_module.get_shared_client()
    second = await mistral_module.get_shared_client()

    assert first is second
    assert first.timeout.read == settings.llm_timeout
    assert first.timeout.connect == settings.llm_connect_timeout


async def test_closing_the_shared_client_clears_the_global(
    isolated_shared_client,
) -> None:
    client = await mistral_module.get_shared_client()

    await close_shared_client()

    assert client.is_closed
    assert mistral_module._shared_client is None


async def test_a_closed_client_is_replaced_rather_than_returned(
    isolated_shared_client,
) -> None:
    """Shutdown/restart inside one process must not hand back a dead client."""
    first = await mistral_module.get_shared_client()
    await first.aclose()

    second = await mistral_module.get_shared_client()

    assert second is not first
    assert not second.is_closed


async def test_closing_is_safe_when_no_client_was_ever_created(
    isolated_shared_client,
) -> None:
    await close_shared_client()

    assert mistral_module._shared_client is None
