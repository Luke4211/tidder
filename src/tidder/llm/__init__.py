from .base import LLMProvider
from .ollama import OllamaProvider

PROVIDERS: dict[str, type[LLMProvider]] = {
    "ollama": OllamaProvider,
}


def get_provider(name: str, **kwargs) -> LLMProvider:
    try:
        cls = PROVIDERS[name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown LLM provider: {name!r}. Known: {sorted(PROVIDERS)}"
        ) from exc
    return cls(**kwargs)


__all__ = ["LLMProvider", "OllamaProvider", "PROVIDERS", "get_provider"]
