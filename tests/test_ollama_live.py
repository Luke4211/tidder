"""Live tests against a real Ollama server.

Skipped by default. Run with:

    RUN_OLLAMA_LIVE=1 \
    TIDDER_LLM_MODEL=llama3.1:8b \
    TIDDER_LLM_HOST=http://<your-host>:11434 \
    pytest tests/test_ollama_live.py -v

These are smoke tests, not assertions about model quality — they verify the
HTTP contract works end-to-end. Useful when iterating on prompts.
"""

from __future__ import annotations

import os

import pytest

from tidder.llm.ollama import OllamaProvider

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_OLLAMA_LIVE") != "1",
    reason="Set RUN_OLLAMA_LIVE=1 to run live Ollama tests.",
)

MODEL = os.environ.get("TIDDER_LLM_MODEL", "llama3.1:8b")
HOST = os.environ.get("TIDDER_LLM_HOST", "http://localhost:11434")


@pytest.fixture
async def provider():
    p = OllamaProvider(model=MODEL, host=HOST, timeout=180.0)
    yield p
    await p.aclose()


async def test_live_classify_obvious_pii(provider: OllamaProvider):
    buckets = [
        "personally identifying information",
        "overtly political rhetoric",
    ]
    scores = await provider.classify(
        "My name is Luke Gorski and my phone is 555-867-5309.",
        buckets,
    )
    print(f"\nPII test scores: {scores}")
    # The PII bucket should clearly win — exact value depends on the model.
    assert scores[0] > scores[1]


async def test_live_classify_subtle_pii(provider: OllamaProvider):
    buckets = [
        "Anything that could possibly constitute personally identifying information.",
        "overtly political rhetoric",
    ]
    scores = await provider.classify(
        "Bill Burr went to the same highschool I did, although he graduated the year before I started highschool.",
        buckets,
    )

    scores_2 = await provider.classify(
        "Tom and Jerry was my favorite cartoon as a kid! I used to watch it every Sunday at my grandmother's house.",
        buckets,
    )

    print(f"\nPII test scores: {scores}")
    assert scores[0] > 0.75
    assert scores_2[0] < 0.25


async def test_live_classify_innocuous(provider: OllamaProvider):
    buckets = [
        "personally identifying information",
        "overtly political rhetoric",
    ]
    scores = await provider.classify(
        "I went to the store yesterday and bought some milk.",
        buckets,
    )
    print(f"\nInnocuous test scores: {scores}")
    assert all(s < 0.5 for s in scores.values())


async def test_live_generate_replacement(provider: OllamaProvider):
    text = await provider.generate_replacement("aww")
    print(f"\nGenerated replacement: {text!r}")
    assert len(text) > 5
    assert "\n" not in text or text.count("\n") < 3  # not a wall of newlines


async def test_live_generate_replacement_variety(provider: OllamaProvider):
    """Two back-to-back calls shouldn't return byte-identical output."""
    a = await provider.generate_replacement("python")
    b = await provider.generate_replacement("python")
    print(f"\nA: {a!r}\nB: {b!r}")
    assert a != b
