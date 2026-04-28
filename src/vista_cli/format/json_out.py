"""JSON rendering for routine and other commands."""

from __future__ import annotations

import json
from typing import Any


def render(obj: dict[str, Any]) -> str:
    """Render a dict as deterministic JSON (sorted keys, 2-space indent)."""
    return json.dumps(obj, indent=2, sort_keys=True, default=str)
