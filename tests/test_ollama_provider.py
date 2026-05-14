"""Tests for OllamaProvider.

These tests use ``httpx.MockTransport`` to fake Ollama's HTTP responses, so
they run fast and offline. To add a new case, drop another handler into
``_make_provider`` (or build a one-off handler inline) and assert on what
``classify`` / ``generate_replacement`` returns or raises.

For a real end-to-end check against a running Ollama instance, see
``test_ollama_live.py`` (skipped by default; opt in with
``RUN_OLLAMA_LIVE=1 pytest``).
"""

from __future__ import annotations

import json
from typing import Callable

import httpx
import pytest

from tidder.llm.ollama import OllamaProvider


# --- helpers ---------------------------------------------------------------


def _make_provider(handler: Callable[[httpx.Request], httpx.Response]) -> OllamaProvider:
    """Build an OllamaProvider whose AsyncClient is backed by a mock transport."""
    provider = OllamaProvider(model="test-model", host="http://test")
    # Swap the real network client for one that calls our handler instead.
    provider._client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )
    return provider


def _chat_response(content: str) -> httpx.Response:
    """Build a 200 response shaped like Ollama's /api/chat envelope."""
    return httpx.Response(
        200,
        json={
            "model": "test-model",
            "message": {"role": "assistant", "content": content},
            "done": True,
        },
    )


# --- classify --------------------------------------------------------------


async def test_classify_happy_path():
    def handler(_req: httpx.Request) -> httpx.Response:
        return _chat_response(json.dumps({"0": 0.92, "1": 0.04}))

    provider = _make_provider(handler)
    scores = await provider.classify("some comment", ["pii", "politics"])

    assert scores == {0: 0.92, 1: 0.04}
    # Keys must be ints, not strings.
    assert all(isinstance(k, int) for k in scores)
    await provider.aclose()


async def test_classify_sends_expected_payload():
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["url"] = str(req.url)
        captured["body"] = json.loads(req.content)
        return _chat_response(json.dumps({"0": 0.1, "1": 0.2}))

    provider = _make_provider(handler)
    await provider.classify("hello world", ["pii", "politics"])

    assert captured["url"].endswith("/api/chat")
    body = captured["body"]
    assert body["model"] == "test-model"
    assert body["format"] == "json"
    assert body["options"]["temperature"] == 0.0
    assert body["stream"] is False
    assert body["messages"][0]["role"] == "system"
    assert "pii" in body["messages"][0]["content"]
    assert "politics" in body["messages"][0]["content"]
    assert body["messages"][1] == {"role": "user", "content": "hello world"}
    await provider.aclose()


async def test_classify_normalizes_whitespace_in_comment():
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.content)
        return _chat_response(json.dumps({"0": 0.5}))

    provider = _make_provider(handler)
    await provider.classify("  hello\n\n  world  \t  ", ["bucket"])

    assert captured["body"]["messages"][1]["content"] == "hello world"
    await provider.aclose()


async def test_classify_raises_on_non_json_content():
    def handler(_req: httpx.Request) -> httpx.Response:
        return _chat_response("not json at all")

    provider = _make_provider(handler)
    with pytest.raises(ValueError, match="Failed to parse response JSON"):
        await provider.classify("comment", ["a"])
    await provider.aclose()


async def test_classify_raises_on_score_out_of_range():
    def handler(_req: httpx.Request) -> httpx.Response:
        return _chat_response(json.dumps({"0": 1.5, "1": 0.2}))

    provider = _make_provider(handler)
    with pytest.raises(ValueError, match="out of range"):
        await provider.classify("comment", ["a", "b"])
    await provider.aclose()


async def test_classify_raises_on_bucket_index_mismatch():
    # Missing bucket 1.
    def handler(_req: httpx.Request) -> httpx.Response:
        return _chat_response(json.dumps({"0": 0.3}))

    provider = _make_provider(handler)
    with pytest.raises(ValueError, match="Expected bucket indices"):
        await provider.classify("comment", ["a", "b"])
    await provider.aclose()


async def test_classify_raises_on_http_error():
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="ollama exploded")

    provider = _make_provider(handler)
    with pytest.raises(httpx.HTTPStatusError):
        await provider.classify("comment", ["a"])
    await provider.aclose()


async def test_classify_raises_on_empty_content():
    def handler(_req: httpx.Request) -> httpx.Response:
        return _chat_response("   ")

    provider = _make_provider(handler)
    with pytest.raises(ValueError, match="message.content"):
        await provider.classify("comment", ["a"])
    await provider.aclose()


# --- generate_replacement --------------------------------------------------


async def test_generate_replacement_happy_path():
    def handler(_req: httpx.Request) -> httpx.Response:
        return _chat_response("Yeah, same here. Coffee's been a lifesaver lately.")

    provider = _make_provider(handler)
    text = await provider.generate_replacement("coffee")

    assert text == "Yeah, same here. Coffee's been a lifesaver lately."
    await provider.aclose()


async def test_generate_replacement_strips_whitespace():
    def handler(_req: httpx.Request) -> httpx.Response:
        return _chat_response("\n\n  hello there.  \n")

    provider = _make_provider(handler)
    text = await provider.generate_replacement("aww")

    assert text == "hello there."
    await provider.aclose()


async def test_generate_replacement_passes_subreddit_in_prompt():
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.content)
        return _chat_response("nice")

    provider = _make_provider(handler)
    await provider.generate_replacement("AskHistorians")

    body = captured["body"]
    assert "r/AskHistorians" in body["messages"][0]["content"]
    # Replacement endpoint should NOT enforce JSON format.
    assert "format" not in body
    # And should use a non-zero temperature for variety.
    assert body["options"]["temperature"] > 0.0
    await provider.aclose()


async def test_generate_replacement_does_not_send_original_body():
    """The replacement contract deliberately excludes the original comment."""
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.content)
        return _chat_response("ok")

    provider = _make_provider(handler)
    await provider.generate_replacement("python")

    # User message should be the generic prompt, not anything comment-shaped.
    user_msg = captured["body"]["messages"][1]["content"]
    assert "Generate a replacement" in user_msg
    await provider.aclose()


async def test_generate_replacement_raises_on_empty_content():
    def handler(_req: httpx.Request) -> httpx.Response:
        return _chat_response("")

    provider = _make_provider(handler)
    with pytest.raises(ValueError, match="message.content"):
        await provider.generate_replacement("anything")
    await provider.aclose()


# --- constructor -----------------------------------------------------------


def test_constructor_rejects_empty_model():
    with pytest.raises(ValueError, match="model name"):
        OllamaProvider(model="")


def test_constructor_strips_trailing_slash_from_host():
    p = OllamaProvider(model="m", host="http://example.com:11434/")
    assert p.host == "http://example.com:11434"
