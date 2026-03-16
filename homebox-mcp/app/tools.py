"""MCP tool definitions for Homebox inventory management."""

from __future__ import annotations

import asyncio
from typing import Any

from fastmcp import FastMCP

from homebox_client import client

mcp = FastMCP("homebox-mcp")

_READONLY_FIELDS = frozenset({"id", "createdAt", "updatedAt"})


def _strip_readonly(data: dict[str, Any], *extra_keys: str) -> dict[str, Any]:
    """Remove read-only/server-managed fields before a PUT request."""
    exclude = _READONLY_FIELDS | set(extra_keys)
    return {k: v for k, v in data.items() if k not in exclude}


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------


@mcp.tool()
async def homebox_list_locations() -> list[dict[str, Any]]:
    """List every location in Homebox (flat list with id, name, and description)."""
    return await client.get_locations()


@mcp.tool()
async def homebox_get_location_tree() -> list[dict[str, Any]]:
    """Return all locations enriched with their nested items.

    Fetches location details in parallel to avoid the N+1 query problem.
    """
    locations = await client.get_locations()
    if not locations:
        return []

    sem = asyncio.Semaphore(10)

    async def _limited_get(loc_id: str) -> dict[str, Any]:
        async with sem:
            return await client.get_location(loc_id)

    details = await asyncio.gather(
        *(_limited_get(loc["id"]) for loc in locations)
    )
    return list(details)


@mcp.tool()
async def homebox_get_location(location_id: str) -> dict[str, Any]:
    """Get full details for a single location including its items.

    Args:
        location_id: UUID of the location.
    """
    return await client.get_location(location_id)


@mcp.tool()
async def homebox_create_location(
    name: str,
    description: str = "",
    parent_id: str | None = None,
) -> dict[str, Any]:
    """Create a new location.

    Args:
        name: Human-readable location name.
        description: Optional description.
        parent_id: Optional parent location UUID for nesting.
    """
    data: dict[str, Any] = {"name": name, "description": description}
    if parent_id:
        data["parent"] = {"id": parent_id}
    return await client.create_location(data)


@mcp.tool()
async def homebox_update_location(
    location_id: str,
    name: str | None = None,
    description: str | None = None,
    parent_id: str | None = None,
) -> dict[str, Any]:
    """Update an existing location.

    Args:
        location_id: UUID of the location to update.
        name: New name (unchanged if omitted).
        description: New description (unchanged if omitted).
        parent_id: New parent location UUID (unchanged if omitted).
    """
    existing = await client.get_location(location_id)
    data = _strip_readonly(existing, "items", "children")
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if parent_id is not None:
        data["parent"] = {"id": parent_id}
    return await client.update_location(location_id, data)


@mcp.tool()
async def homebox_delete_location(location_id: str) -> str:
    """Delete a location. Items in this location are NOT automatically moved.

    Args:
        location_id: UUID of the location to delete.
    """
    await client.delete_location(location_id)
    return f"Location {location_id} deleted."


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------


@mcp.tool()
async def homebox_list_items(
    location_id: str | None = None,
    label_id: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """List items with optional filters. All pages are returned automatically.

    Args:
        location_id: Filter by location UUID.
        label_id: Filter by label UUID.
        search: Free-text search string.
    """
    return await client.get_items(
        location_id=location_id, label_id=label_id, search=search
    )


@mcp.tool()
async def homebox_get_item(item_id: str) -> dict[str, Any]:
    """Get full details for a single item including custom fields and attachments.

    Args:
        item_id: UUID of the item.
    """
    return await client.get_item(item_id)


_MAX_QUERY_LENGTH = 500


@mcp.tool()
async def homebox_search(query: str) -> list[dict[str, Any]]:
    """Full-text search across all items in Homebox.

    Args:
        query: Search string (matched against name, description, notes, and fields).
    """
    if len(query) > _MAX_QUERY_LENGTH:
        query = query[:_MAX_QUERY_LENGTH]
    return await client.search_items(query)


@mcp.tool()
async def homebox_create_item(
    name: str,
    location_id: str,
    description: str = "",
    label_ids: list[str] | None = None,
    quantity: int = 1,
) -> dict[str, Any]:
    """Create a new inventory item.

    Args:
        name: Item name.
        location_id: UUID of the location to place the item in.
        description: Optional description.
        label_ids: Optional list of label UUIDs to attach.
        quantity: Number of this item (default 1).
    """
    data: dict[str, Any] = {
        "name": name,
        "description": description,
        "location": {"id": location_id},
        "quantity": quantity,
    }
    if label_ids:
        data["labels"] = [{"id": lid} for lid in label_ids]
    return await client.create_item(data)


@mcp.tool()
async def homebox_update_item(
    item_id: str,
    name: str | None = None,
    description: str | None = None,
    location_id: str | None = None,
    label_ids: list[str] | None = None,
    quantity: int | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Update an item using GET-then-PUT so that unspecified fields are preserved.

    Only pass the fields you want to change; everything else stays as-is.

    Args:
        item_id: UUID of the item.
        name: New name.
        description: New description.
        location_id: Move to this location UUID.
        label_ids: Replace labels with this list of UUIDs.
        quantity: New quantity.
        notes: New notes text.
    """
    updates: dict[str, Any] = {}
    if name is not None:
        updates["name"] = name
    if description is not None:
        updates["description"] = description
    if location_id is not None:
        updates["location"] = {"id": location_id}
    if label_ids is not None:
        updates["labels"] = [{"id": lid} for lid in label_ids]
    if quantity is not None:
        updates["quantity"] = quantity
    if notes is not None:
        updates["notes"] = notes
    return await client.update_item(item_id, updates)


@mcp.tool()
async def homebox_move_item(item_id: str, location_id: str) -> dict[str, Any]:
    """Move an item to a different location (preserves all other fields).

    Args:
        item_id: UUID of the item to move.
        location_id: UUID of the destination location.
    """
    return await client.move_item(item_id, location_id)


@mcp.tool()
async def homebox_delete_item(item_id: str) -> str:
    """Permanently delete an item.

    Args:
        item_id: UUID of the item to delete.
    """
    await client.delete_item(item_id)
    return f"Item {item_id} deleted."


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------


@mcp.tool()
async def homebox_list_labels() -> list[dict[str, Any]]:
    """List all labels in Homebox."""
    return await client.get_labels()


@mcp.tool()
async def homebox_create_label(
    name: str, description: str = "", color: str = ""
) -> dict[str, Any]:
    """Create a new label.

    Args:
        name: Label name.
        description: Optional description.
        color: Optional hex color (e.g. '#ff0000').
    """
    data: dict[str, Any] = {"name": name, "description": description}
    if color:
        data["color"] = color
    return await client.create_label(data)


@mcp.tool()
async def homebox_update_label(
    label_id: str,
    name: str | None = None,
    description: str | None = None,
    color: str | None = None,
) -> dict[str, Any]:
    """Update an existing label.

    Args:
        label_id: UUID of the label.
        name: New name.
        description: New description.
        color: New hex color.
    """
    existing = await client.get_label(label_id)
    data = _strip_readonly(existing, "items")
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if color is not None:
        data["color"] = color
    return await client.update_label(label_id, data)


@mcp.tool()
async def homebox_delete_label(label_id: str) -> str:
    """Delete a label. Items keep their other labels.

    Args:
        label_id: UUID of the label to delete.
    """
    await client.delete_label(label_id)
    return f"Label {label_id} deleted."


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


@mcp.tool()
async def homebox_get_statistics() -> dict[str, Any]:
    """Return Homebox group statistics (total items, locations, labels, value)."""
    return await client.get_statistics()
