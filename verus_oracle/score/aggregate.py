from __future__ import annotations

from dataclasses import dataclass

from ..features import FunctionFeatures, StaticFeatures
from ..llm.questions import ProbeAnswer
from ..llm.router import RankedPattern
from .buckets import difficulty_bucket, duration_bucket
from .duration_proxy import predict_elapsed_seconds

# Initial per-pattern base difficulty (1.0 easy -> 5.0 hard). Calibrate against
# HAB outcomes via `validate/` once seed data lands in `data/`.
_PATTERN_DIFFICULTY: dict[str, float] = {
    "R1": 2.5,
    "R2": 2.0,
    "R3": 3.5,
    "R4": 2.5,
    "R5": 3.0,
    "R7": 3.5,
    "R8": 2.0,
    "R9": 3.0,
    "R10": 1.5,
    "R11": 2.0,
}

_BUCKET_RANK = {"easy": 0, "medium": 1, "hard": 2}


@dataclass(frozen=True)
class FunctionVerdict:
    function: str
    bucket: str
    predicted_pattern: str
    top_confidence: float
    est_duration_s: float
    duration_bucket: str
    ranked: tuple[RankedPattern, ...]
    probes: tuple[ProbeAnswer, ...]
    features: FunctionFeatures

    def to_dict(self) -> dict:
        return {
            "function": self.function,
            "bucket": self.bucket,
            "predicted_pattern": self.predicted_pattern,
            "top_confidence": round(self.top_confidence, 2),
            "est_duration_s": round(self.est_duration_s, 1),
            "duration_bucket": self.duration_bucket,
            "ranked": [
                {"pattern": r.pattern, "confidence": round(r.confidence, 2)}
                for r in self.ranked
            ],
            "probes": [
                {
                    "qid": p.qid,
                    "answer": p.answer,
                    "delta": round(p.delta, 2),
                }
                for p in self.probes
            ],
            "features": self.features.to_dict(),
        }


@dataclass(frozen=True)
class Verdict:
    """File-level rollup. `.functions` carries per-function detail."""

    file_path: str
    bucket: str
    predicted_pattern: str
    est_duration_s: float
    duration_bucket: str
    functions: tuple[FunctionVerdict, ...]

    def to_dict(self) -> dict:
        return {
            "file": self.file_path,
            "bucket": self.bucket,
            "predicted_pattern": self.predicted_pattern,
            "est_duration_s": round(self.est_duration_s, 1),
            "duration_bucket": self.duration_bucket,
            "functions": [f.to_dict() for f in self.functions],
        }


def _confidence_weighted_difficulty(ranked: tuple[RankedPattern, ...]) -> float:
    total = sum(r.confidence for r in ranked) or 1.0
    return sum(_PATTERN_DIFFICULTY.get(r.pattern, 3.0) * r.confidence for r in ranked) / total


def _feature_adjustment(features: FunctionFeatures) -> float:
    return (
        0.05 * features.iterator_combinators
        + 0.03 * features.method_chain_calls
        + 0.01 * features.loc
        + 0.10 * features.unary_negations
    )


def score_function(
    features: FunctionFeatures,
    ranked: tuple[RankedPattern, ...],
    probes: tuple[ProbeAnswer, ...] = (),
) -> FunctionVerdict:
    if ranked:
        base = _confidence_weighted_difficulty(ranked)
        top = ranked[0]
    else:
        base = 3.0
        top = RankedPattern(pattern="R2", confidence=0.0)
    probe_delta = sum(p.delta for p in probes)
    difficulty = max(1.0, min(5.0, base + _feature_adjustment(features) + probe_delta))
    elapsed = predict_elapsed_seconds(features, top.pattern, difficulty)
    return FunctionVerdict(
        function=features.name,
        bucket=difficulty_bucket(difficulty),
        predicted_pattern=top.pattern,
        top_confidence=top.confidence,
        est_duration_s=elapsed,
        duration_bucket=duration_bucket(elapsed),
        ranked=ranked,
        probes=probes,
        features=features,
    )


def rollup(static: StaticFeatures, function_verdicts: tuple[FunctionVerdict, ...]) -> Verdict:
    if not function_verdicts:
        return Verdict(
            file_path=static.path,
            bucket="easy",
            predicted_pattern="R2",
            est_duration_s=0.0,
            duration_bucket="easy",
            functions=(),
        )
    worst = max(function_verdicts, key=lambda v: _BUCKET_RANK[v.bucket])
    worst_dur = max(function_verdicts, key=lambda v: _BUCKET_RANK[v.duration_bucket])
    total_s = sum(v.est_duration_s for v in function_verdicts)
    return Verdict(
        file_path=static.path,
        bucket=worst.bucket,
        predicted_pattern=worst.predicted_pattern,
        est_duration_s=total_s,
        duration_bucket=worst_dur.duration_bucket,
        functions=function_verdicts,
    )
