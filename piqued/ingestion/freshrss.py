"""Async GReader API client for FreshRSS article ingestion."""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from piqued import config

logger = logging.getLogger(__name__)


@dataclass
class FeedItem:
    """Parsed article from GReader API."""

    item_id: str
    feed_id: str
    title: str
    url: str
    content_html: str
    published_at: datetime | None


class FreshRSSClient:
    """Async GReader API client with auth token management."""

    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        api_pass: str | None = None,
    ):
        self.base_url = (base_url or config.get("freshrss_base_url")).rstrip("/")
        self.username = username or config.get("freshrss_username")
        self.api_pass = api_pass or config.get("freshrss_api_pass")
        self._token: str | None = None
        self._client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self._client.aclose()

    async def _authenticate(self) -> str:
        """Get GReader API auth token."""
        resp = await self._client.post(
            f"{self.base_url}/api/greader.php/accounts/ClientLogin",
            data={"Email": self.username, "Passwd": self.api_pass},
        )
        resp.raise_for_status()
        for line in resp.text.strip().split("\n"):
            if line.startswith("Auth="):
                token = line.split("=", 1)[1]
                self._token = token
                return token
        raise RuntimeError(f"Auth failed: {resp.text}")

    async def _get_token(self) -> str:
        if self._token is None:
            await self._authenticate()
        return self._token  # type: ignore[return-value]

    async def _api_get(self, path: str, params: dict | None = None) -> dict:
        """Authenticated GET, re-auth on 401."""
        token = await self._get_token()
        resp = await self._client.get(
            f"{self.base_url}/api/greader.php/{path}",
            params=params,
            headers={"Authorization": f"GoogleLogin auth={token}"},
        )
        if resp.status_code == 401:
            logger.info("GReader token expired, re-authenticating")
            self._token = None
            token = await self._get_token()
            resp = await self._client.get(
                f"{self.base_url}/api/greader.php/{path}",
                params=params,
                headers={"Authorization": f"GoogleLogin auth={token}"},
            )
        resp.raise_for_status()
        return resp.json()

    async def get_subscriptions(self) -> list[dict]:
        """Get all subscribed feeds."""
        data = await self._api_get("reader/api/0/subscription/list", {"output": "json"})
        return data.get("subscriptions", [])

    async def get_stream_items(
        self,
        stream_id: str,
        count: int = 50,
        exclude_read: bool = True,
        continuation: str | None = None,
    ) -> tuple[list[FeedItem], str | None]:
        """Fetch items from a feed stream with pagination.

        Args:
            stream_id: GReader feed stream ID.
            count: Max items per page.
            exclude_read: If True, only fetch unread items.
            continuation: Pagination token from previous call.

        Returns:
            Tuple of (items, next_continuation). next_continuation is None if no more pages.
        """
        params: dict = {"output": "json", "n": str(count)}
        if exclude_read:
            params["xt"] = "user/-/state/com.google/read"
        if continuation:
            params["c"] = continuation

        data = await self._api_get(f"reader/api/0/stream/contents/{stream_id}", params)

        items = []
        for entry in data.get("items", []):
            content = entry.get("summary", {}).get("content", "")
            published = None
            if "published" in entry:
                try:
                    published = datetime.fromtimestamp(
                        entry["published"], tz=timezone.utc
                    )
                except (ValueError, OSError):
                    pass

            # Extract canonical URL
            url = ""
            for alt in entry.get("alternate", []):
                if alt.get("type") == "text/html":
                    url = alt.get("href", "")
                    break
            if not url:
                url = (
                    entry.get("canonical", [{}])[0].get("href", "")
                    if entry.get("canonical")
                    else ""
                )

            items.append(
                FeedItem(
                    item_id=entry.get("id", ""),
                    feed_id=entry.get("origin", {}).get("streamId", ""),
                    title=entry.get("title", "Untitled"),
                    url=url,
                    content_html=content,
                    published_at=published,
                )
            )

        next_continuation = data.get("continuation")
        return items, next_continuation

    async def get_all_stream_items(
        self,
        stream_id: str,
        max_items: int = 200,
        exclude_read: bool = True,
    ) -> list[FeedItem]:
        """Fetch all items from a stream, handling pagination.

        Args:
            stream_id: GReader feed stream ID.
            max_items: Safety cap on total items fetched.
            exclude_read: If True, only fetch unread items.

        Returns:
            List of all fetched items.
        """
        all_items: list[FeedItem] = []
        continuation: str | None = None

        while len(all_items) < max_items:
            batch_size = min(50, max_items - len(all_items))
            items, continuation = await self.get_stream_items(
                stream_id,
                count=batch_size,
                exclude_read=exclude_read,
                continuation=continuation,
            )
            all_items.extend(items)

            if not continuation or not items:
                break

        return all_items
