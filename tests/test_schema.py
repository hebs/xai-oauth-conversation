"""Tests for xAI tool-schema normalization."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


SCHEMA_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "xai_oauth_conversation"
    / "schema.py"
)
SPEC = importlib.util.spec_from_file_location("xai_schema", SCHEMA_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
normalize_tool_schema = MODULE.normalize_tool_schema


class NormalizeToolSchemaTest(unittest.TestCase):
    """Verify schemas remain valid while satisfying xAI root rules."""

    def test_adds_object_type_to_required_union_branches(self) -> None:
        """Timer duration alternatives are explicitly object typed."""
        source = {
            "type": "object",
            "properties": {
                "hours": {"type": "integer"},
                "minutes": {"type": "integer"},
                "seconds": {"type": "integer"},
            },
            "required": [],
            "anyOf": [
                {"required": ["hours"]},
                {"required": ["minutes"]},
                {"required": ["seconds"]},
            ],
        }

        normalized = normalize_tool_schema(source)

        self.assertTrue(
            all(branch["type"] == "object" for branch in normalized["anyOf"])
        )
        self.assertNotIn("type", source["anyOf"][0])

    def test_leaves_scalar_union_branches_unchanged(self) -> None:
        """Do not silently change genuine scalar alternatives."""
        source = {
            "type": "object",
            "oneOf": [{"type": "string"}, {"type": "object"}],
        }

        self.assertEqual(normalize_tool_schema(source), source)


if __name__ == "__main__":
    unittest.main()
