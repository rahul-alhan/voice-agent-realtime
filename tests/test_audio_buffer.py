"""Lightweight tests — no mic, no network."""
from __future__ import annotations

import json

from voice_agent.tools import TOOL_SPECS, execute


def test_tool_specs_well_formed():
    assert len(TOOL_SPECS) >= 1
    for spec in TOOL_SPECS:
        assert spec["type"] == "function"
        assert "name" in spec
        assert "parameters" in spec


def test_unknown_tool_returns_error():
    out = json.loads(execute("nope", {}))
    assert out.get("error") == "unknown_tool"
