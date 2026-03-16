"""Async HTTP client for the Homebox API with pagination, retry, and safe updates."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from config import config

logger = logging.getLogger(__name__)

_TRANSIENT_STATUS_CODES = frozenset(range(500, 600))
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_MAX_PAGE_SIZE = 100


class HomeboxClient:
    """Thin async wrapper around the Homebox REST API (v1)."""

    def __init__(self) -> None:
        self._base = f"{config.homebox_url}/api/v1"
        self._headers = {"Authorization": f"Bearer {config.homebox_token}"}
        self._client: httpx.AsyncClient | None = None

    # -- lifecycle ------------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base,
                headers=self._headers,
                timeout=_TIMEOUT,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # -- low-level request with one retry on transient errors -----------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
    ) -> httpx.Response:
        client = await self._get_client()
        last_exc: Exception | None = None

        for attempt in range(2):  # initial + 1 retry
            try:
                resp = await client.request(
                    method, path, params=params, json=json
                )
                if resp.status_code in _TRANSIENT_STATUS_CODES and attempt == 0:
                    logger.warning(
                        "Transient %s on %s %s, retrying",
                        resp.status_code,
                        method,
                        path,
                    )
                    continue
                resp.raise_for_status()
                return resp
            except (httpx.ConnectError, httpx.ReadTimeout) as exc:
                last_exc = exc
                if attempt == 0:
                    logger.warning(
                        "Connection error on %s %s, retrying: %s",
                        method,
                        path,
                        exc,
                    )
                    # Force a fresh connection on retry.
                    await self.close()
                    client = await self._get_client()
                    continue
                raise
        # Should not be reached, but satisfy the type checker.
        raise last_exc  # type: ignore[misc]

    async def _get(self, path: str, **kwargs: Any) -> Any:
        resp = await self._request("GET", path, **kwargs)
        return resp.json()

    async def _post(self, path: str, **kwargs: Any) -> Any:
        resp = await self._request("POST", path, **kwargs)
        return resp.json()

    async def _put(self, path: str, **kwargs: Any) -> Any:
        resp = await self._request("PUT", path, **kwargs)
        return resp.json()

    async def _delete(self, path: str) -> None:
        await self._request("DELETE", path)

    # -- paginated GET --------------------------------------------------------

    async def _get_paginated(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch all pages from a paginated Homebox endpoint."""
        all_items: list[dict[str, Any]] = []
        page = 1
        params = dict(params or {})

        while True:
            params["page"] = page
            params["pageSize"] = _MAX_PAGE_SIZE
            resp = await self._request("GET", path, params=params)
            body = resp.json()

            items = body.get("items", [])
            all_items.extend(items)

            total = body.get("total", len(all_items))
            if len(all_items) >= total or len(items) < _MAX_PAGE_SIZE:
                break
            page += 1

        return all_items

    # -- locations ------------------------------------------------------------

    async def get_locations(self) -> list[dict[str, Any]]:
        """Return all locations (flat list)."""
        return await self._get("/locations")

    async def get_location(self, location_id: str) -> dict[str, Any]:
        """Return a single location with its items."""
        return await self._get(f"/locations/{location_id}")

    async def create_location(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new location."""
        return await self._post("/locations", json=data)

    async def update_location(
        self, location_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing location (partial merge)."""
        return await self._put(f"/locations/{location_id}", json=data)

    async def delete_location(self, location_id: str) -> None:
        """Delete a location."""
        await self._delete(f"/locations/{location_id}")

    # -- items ----------------------------------------------------------------

    async def get_items(
        self,
        *,
        location_id: str | None = None,
        label_id: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return items with full pagination. Supports optional filters."""
        params: dict[str, Any] = {}
        if location_id:
            params["locations"] = location_id
        if label_id:
            params["labels"] = label_id
        if search:
            params["q"] = search
        return await self._get_paginated("/items", params=params)

    async def get_item(self, item_id: str) -> dict[str, Any]:
        """Return the full detail for a single item."""
        return await self._get(f"/items/{item_id}")

    async def create_item(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new item."""
        return await self._post("/items", json=data)

    async def update_item(
        self, item_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        """GET-then-PUT update that preserves all existing fields.

        Only the keys present in *updates* are overwritten; every other
        field is kept as-is so nothing is accidentally blanked out.
        """
        existing = await self.get_item(item_id)
        merged = {**existing, **updates}
        # Remove read-only / server-managed keys that the API rejects.
        for key in ("createdAt", "updatedAt", "id"):
            merged.pop(key, None)
        return await self._put(f"/items/{item_id}", json=merged)

    async def delete_item(self, item_id: str) -> None:
        """Delete an item."""
        await self._delete(f"/items/{item_id}")

    async def move_item(
        self, item_id: str, location_id: str
    ) -> dict[str, Any]:
        """Move an item to a different location via update."""
        return await self.update_item(
            item_id, {"location": {"id": location_id}}
        )

    # -- search ---------------------------------------------------------------

    async def search_items(self, query: str) -> list[dict[str, Any]]:
        """Full-text search using Homebox's q parameter."""
        return await self._get_paginated("/items", params={"q": query})

    # -- labels ---------------------------------------------------------------

    async def get_labels(self) -> list[dict[str, Any]]:
        """Return all labels."""
        return await self._get("/labels")

    async def create_label(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new label."""
        return await self._post("/labels", json=data)

    async def update_label(
        self, label_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing label."""
        return await self._put(f"/labels/{label_id}", json=data)

    async def delete_label(self, label_id: str) -> None:
        """Delete a label."""
        await self._delete(f"/labels/{label_id}")

    # -- statistics -----------------------------------------------------------

    async def get_statistics(self) -> dict[str, Any]:
        """Return Homebox group statistics."""
        return await self._get("/groups/statistics")


client = HomeboxClient()
