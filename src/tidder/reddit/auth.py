"""Reddit OAuth: interactive first-run, refresh-token-driven thereafter.

On first ``remove``, run the interactive OAuth dance and persist the refresh
token to ``~/.config/tidder/credentials.json`` (mode ``0600``). Every
subsequent run silently exchanges the refresh token for a fresh access
token; only re-prompt if the refresh token has been revoked or expired.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..config import CREDENTIALS_FILE


@dataclass(slots=True)
class StoredCredentials:
    refresh_token: str
    client_id: str
    scope: str


def load_credentials(path: Path = CREDENTIALS_FILE) -> StoredCredentials | None:
    """Return persisted credentials, or ``None`` if no file is present. Stub."""
    raise NotImplementedError("reddit.auth.load_credentials is not implemented yet.")


def save_credentials(creds: StoredCredentials, path: Path = CREDENTIALS_FILE) -> None:
    """Persist credentials at mode ``0600``. Stub."""
    raise NotImplementedError("reddit.auth.save_credentials is not implemented yet.")


async def interactive_oauth() -> StoredCredentials:
    """Run the one-time interactive OAuth dance. Stub."""
    raise NotImplementedError("reddit.auth.interactive_oauth is not implemented yet.")


async def fetch_access_token(creds: StoredCredentials) -> str:
    """Exchange a refresh token for a short-lived access token. Stub."""
    raise NotImplementedError("reddit.auth.fetch_access_token is not implemented yet.")
