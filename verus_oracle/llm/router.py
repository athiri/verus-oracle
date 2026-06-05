from __future__ import annotations

import json
from dataclasses import dataclass

from ..taxonomy import PATTERN_IDS, load_router_prompt
from .client import LLMClient

_ROUTER_SCHEMA = {
    "type": "object",
    "properties": {
        "ranked": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "enum": list(PATTERN_IDS)},
                    "confidence": {"type": "number"},
                },
                "required": ["pattern", "confidence"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["ranked"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class RankedPattern:
    pattern: str
    confidence: float


def classify(snippet: str, client: LLMClient) -> tuple[RankedPattern, ...]:
    """Run the router prompt on a Rust snippet, return the ranked R-id list."""
    system = load_router_prompt()
    response = client.call(
        system=system,
        user=snippet,
        max_tokens=256,
        output_schema=_ROUTER_SCHEMA,
    )
    payload = json.loads(response.text)
    return tuple(
        RankedPattern(pattern=item["pattern"], confidence=float(item["confidence"]))
        for item in payload["ranked"]
    )
