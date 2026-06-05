import json
from dataclasses import dataclass

from verus_oracle.llm.questions import (
    PROBES_BY_PATTERN,
    difficulty_delta,
    probe_pattern,
)
from verus_oracle.pipeline import score_source


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


def test_probe_pattern_parses_yes_no_answers():
    client = _StubClient({
        "answers": [
            {"qid": "R3.closed_mut", "answer": True},
            {"qid": "R3.dynamic_count", "answer": False},
            {"qid": "R3.unknown_len", "answer": True},
        ]
    })
    probes = probe_pattern("R3", "xs.iter().fold(0, |a, x| a + x)", client)
    assert len(probes) == 3
    by_qid = {p.qid: p for p in probes}
    assert by_qid["R3.closed_mut"].answer is True
    assert by_qid["R3.closed_mut"].delta > 0
    assert by_qid["R3.dynamic_count"].answer is False
    assert by_qid["R3.dynamic_count"].delta == 0.0


def test_difficulty_delta_sums_deltas():
    client = _StubClient({
        "answers": [{"qid": q.qid, "answer": True} for q in PROBES_BY_PATTERN["R3"]]
    })
    probes = probe_pattern("R3", "snippet", client)
    expected = sum(q.delta_if_yes for q in PROBES_BY_PATTERN["R3"])
    assert difficulty_delta(probes) == expected


def test_score_source_with_stubbed_router_and_probes():
    """End-to-end LLM path with both stages stubbed."""

    def stub_classify(snippet, client):
        from verus_oracle.llm.router import RankedPattern
        return (RankedPattern("R3", 0.9), RankedPattern("R2", 0.2))

    def stub_probe(pattern, snippet, client):
        from verus_oracle.llm.questions import ProbeAnswer
        return (ProbeAnswer("R3.closed_mut", "x", True, 0.8),)

    source = "fn iter_sum(xs: &[u64]) -> u64 { xs.iter().fold(0u64, |a, x| a + x) }"
    v = score_source(
        source,
        client=_StubClient({}),
        classify_fn=stub_classify,
        probe_fn=stub_probe,
    )
    assert len(v.functions) == 1
    fv = v.functions[0]
    assert fv.predicted_pattern == "R3"
    assert len(fv.probes) == 1
    assert fv.probes[0].qid == "R3.closed_mut"
