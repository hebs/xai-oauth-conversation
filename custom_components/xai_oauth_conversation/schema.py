"""JSON schema compatibility helpers for the xAI API."""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def normalize_tool_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return an xAI-compatible object-root tool schema.

    voluptuous-openapi represents ``vol.Any`` keys as root ``anyOf`` branches
    containing only a ``required`` constraint. Those branches inherit the
    surrounding object type in JSON Schema, but xAI validates each root union
    branch independently and rejects them as non-object branches.
    """
    normalized = deepcopy(schema)
    if normalized.get("type") != "object":
        return normalized

    for union_key in ("anyOf", "oneOf"):
        branches = normalized.get(union_key)
        if not isinstance(branches, list):
            continue
        for branch in branches:
            if not isinstance(branch, dict) or "type" in branch:
                continue
            if any(
                key in branch
                for key in ("required", "properties", "additionalProperties")
            ):
                branch["type"] = "object"

    return normalized
