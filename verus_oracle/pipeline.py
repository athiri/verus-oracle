from __future__ import annotations

from pathlib import Path

from .features import extract_features
from .features.tree_sitter import extract_from_path
from .llm import LLMClient, classify, probe_pattern
from .score import Verdict, rollup, score_function


def _score_one(fn, client, *, use_probes: bool, classify_fn, probe_fn):
    ranked = classify_fn(fn.body, client)
    probes = ()
    if use_probes and ranked:
        probes = probe_fn(ranked[0].pattern, fn.body, client)
    return score_function(fn, ranked, probes)


def score_source(
    source: str,
    *,
    path: str = "<inline>",
    client: LLMClient | None = None,
    offline: bool = False,
    use_probes: bool = True,
    classify_fn=classify,
    probe_fn=probe_pattern,
) -> Verdict:
    """Score a Rust source string. `offline=True` skips all LLM calls.
    `use_probes=False` keeps the router call but skips per-pattern probes.
    """
    static = extract_features(source, path=path)
    if offline:
        verdicts = tuple(score_function(fn, ()) for fn in static.functions)
        return rollup(static, verdicts)

    if client is None:
        client = LLMClient()
    verdicts = tuple(
        _score_one(fn, client, use_probes=use_probes, classify_fn=classify_fn, probe_fn=probe_fn)
        for fn in static.functions
    )
    return rollup(static, verdicts)


def score_file(
    path: str | Path,
    *,
    client: LLMClient | None = None,
    offline: bool = False,
    use_probes: bool = True,
    classify_fn=classify,
    probe_fn=probe_pattern,
) -> Verdict:
    """Score a Rust file by path."""
    static = extract_from_path(path)
    if offline:
        verdicts = tuple(score_function(fn, ()) for fn in static.functions)
        return rollup(static, verdicts)

    if client is None:
        client = LLMClient()
    verdicts = tuple(
        _score_one(fn, client, use_probes=use_probes, classify_fn=classify_fn, probe_fn=probe_fn)
        for fn in static.functions
    )
    return rollup(static, verdicts)
