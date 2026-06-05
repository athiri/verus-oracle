import json
from dataclasses import dataclass

from verus_oracle.llm.router import classify, RankedPattern


@dataclass
class _StubResponse:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


class _StubClient:
    def __init__(self, payload: dict):
        self._payload = payload
        self.calls: list[tuple[str, str]] = []

    def call(self, *, system, user, max_tokens, output_schema=None):
        self.calls.append((system, user))
        return _StubResponse(text=json.dumps(self._payload))


def test_classify_parses_ranked():
    client = _StubClient({
        "ranked": [
            {"pattern": "R3", "confidence": 0.9},
            {"pattern": "R2", "confidence": 0.3},
        ]
    })
    ranked = classify("xs.iter().map(|x| x + 1).collect()", client)
    assert ranked == (
        RankedPattern("R3", 0.9),
        RankedPattern("R2", 0.3),
    )
    assert len(client.calls) == 1
