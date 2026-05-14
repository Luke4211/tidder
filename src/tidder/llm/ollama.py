"""Ollama-backed LLM provider.

Currently a stub: the methods raise ``NotImplementedError`` and exist so the
rest of the pipeline can wire up against the provider interface.
"""

from __future__ import annotations

import httpx

import json

from .base import LLMProvider


class OllamaProvider(LLMProvider):
    def __init__(
        self,
        model: str,
        host: str = "http://localhost:11434",
        timeout: float = 120.0,
    ) -> None:
        if not model:
            raise ValueError("OllamaProvider requires a model name.")
        self.model = model
        self.host = host.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.host, timeout=timeout)

    def _build_payload(self, comment_body: str, buckets: list[str]) -> dict:
        """Construct the JSON payload for the Ollama API."""
        system_prompt = (
            "You are a classifier. You will receive a list of content buckets (each with a "
            "description) and a single Reddit comment. For every bucket, estimate the "
            "probability that the comment falls into that bucket as a float in [0.0, 1.0], "
            'where 0.00 means "definitely does not belong" and 1.00 means "definitely '
            'belongs". Scores across buckets are independent — they do not need to sum to 1.\n\n'
            f"Buckets:\n"
            + "\n".join(f"{i}: {bucket}" for i, bucket in enumerate(buckets))
            + "\n\n"
            "Respond with a single JSON object mapping bucket index (as a string) to score. "
            'No prose, no markdown, no commentary. Example: {"0": 0.92, "1": 0.04, "2": 0.31}'
        )

        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": comment_body},
            ],
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.0},
        }

    async def classify(
        self,
        comment_body: str,
        buckets: list[str],
    ) -> dict[int, float]:
        body = comment_body.strip()
        body = " ".join(body.split())

        payload = self._build_payload(body, buckets)
        response = await self._client.post("/api/chat", json=payload)
        response.raise_for_status()
        try:
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("Response JSON is not an object.")

            content_str = data.get("message", {}).get("content", "").strip()

            if not content_str:
                raise ValueError(
                    "Response JSON does not contain 'message.content' or it is empty."
                )
            parsed = json.loads(content_str)
            if not isinstance(parsed, dict):
                raise ValueError("Model output is not a JSON object.")

            parsed = {int(k): float(v) for k, v in parsed.items()}

            for idx, score in parsed.items():
                if not 0.0 <= score <= 1.0:
                    raise ValueError(f"Score for bucket {idx} is out of range: {score}")
            if set(parsed.keys()) != set(range(len(buckets))):
                raise ValueError(
                    f"Expected bucket indices {list(range(len(buckets)))}, got {sorted(parsed.keys())}"
                )
            return parsed

        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Failed to parse response JSON: {e}\nResponse text: {response.text}"
            ) from e

    async def generate_replacement(self, subreddit: str) -> str:
        system_prompt = (
            "You are generating replacement text for a Reddit comment that is "
            "being overwritten for privacy reasons. Write a single short, "
            "generic, politically neutral comment (1-3 sentences) that would "
            "be plausible in the given subreddit.\n\n"
            "Avoid:\n"
            "- specific names, places, dates, or numbers\n"
            "- strong opinions on any political, religious, or social topic\n"
            "- references to drugs, sex, violence, or crime\n"
            "- anything that could be construed as advice\n\n"
            "The replacement should read like a low-effort, throwaway comment "
            "from a casual user. Vary your output - do not repeat phrasing "
            "across comments.\n\n"
            f"Subreddit: r/{subreddit}"
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": "Generate a replacement comment for this subreddit.",
                },
            ],
            "stream": False,
            "options": {"temperature": 0.8},
        }
        response = await self._client.post("/api/chat", json=payload)
        response.raise_for_status()
        try:
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("Response JSON is not an object.")

            content_str = data.get("message", {}).get("content", "").strip()
            if not content_str:
                raise ValueError(
                    "Response JSON does not contain 'message.content' or it is empty."
                )
            return content_str
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Failed to parse response JSON: {e}\nResponse text: {response.text}"
            ) from e

    async def aclose(self) -> None:
        await self._client.aclose()
