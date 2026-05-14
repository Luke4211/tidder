"""Replacement-body generators for ``remove --mode overwrite``.

Three styles:

- ``random``: locally-generated random text, unique per comment.
- ``llm``: provider-generated generic, neutral, plausible replacement.
- ``fixed``: a single user-supplied constant string.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .llm.base import LLMProvider


class Overwriter(ABC):
    @abstractmethod
    async def generate(self, original_body: str) -> str: ...


class RandomOverwriter(Overwriter):
    async def generate(self, original_body: str) -> str:
        raise NotImplementedError("RandomOverwriter.generate is not implemented yet.")


class FixedOverwriter(Overwriter):
    def __init__(self, text: str) -> None:
        if not text:
            raise ValueError("FixedOverwriter requires non-empty text.")
        self.text = text

    async def generate(self, original_body: str) -> str:
        return self.text


class LLMOverwriter(Overwriter):
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    async def generate(self, original_body: str) -> str:
        return await self.provider.generate_replacement(original_body)


def build_overwriter(
    style: str,
    *,
    fixed_text: str | None = None,
    provider: LLMProvider | None = None,
) -> Overwriter:
    match style:
        case "random":
            return RandomOverwriter()
        case "fixed":
            if fixed_text is None:
                raise ValueError("--overwrite-style fixed requires --overwrite-text.")
            return FixedOverwriter(fixed_text)
        case "llm":
            if provider is None:
                raise ValueError("--overwrite-style llm requires an LLM provider.")
            return LLMOverwriter(provider)
        case _:
            raise ValueError(f"Unknown overwrite style: {style!r}")
