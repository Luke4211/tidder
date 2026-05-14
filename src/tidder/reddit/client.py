"""Rate-limited async Reddit API client used by ``remove``.

Wraps OAuth-authenticated calls in an ``aiolimiter`` so we stay inside
Reddit's published API limits, with backoff on 429s.
"""

from __future__ import annotations

import httpx
from aiolimiter import AsyncLimiter

REDDIT_API_BASE = "https://oauth.reddit.com"


class RedditClient:
    def __init__(
        self,
        access_token: str,
        *,
        user_agent: str = "tidder/0.0.1",
        rate_limit_per_minute: int = 60,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=REDDIT_API_BASE,
            headers={
                "Authorization": f"bearer {access_token}",
                "User-Agent": user_agent,
            },
            timeout=30.0,
        )
        self._limiter = AsyncLimiter(rate_limit_per_minute, 60)

    async def overwrite_comment(self, comment_id: str, new_body: str) -> None:
        raise NotImplementedError(
            "RedditClient.overwrite_comment is not implemented yet."
        )

    async def delete_comment(self, comment_id: str) -> None:
        raise NotImplementedError(
            "RedditClient.delete_comment is not implemented yet."
        )

    async def aclose(self) -> None:
        await self._client.aclose()
