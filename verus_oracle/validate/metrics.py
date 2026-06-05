"""Calibration metrics against ground truth.

v1 reports:
  - Difficulty-bucket accuracy (predicted vs ground-truth bucket from `elapsed_s`).
  - Mean absolute error on log(elapsed_s).
  - Top-1 / top-2 pattern accuracy (when GT pattern is present).

Once duration_proxy is fit on real data, swap in proper AUC / quantile loss.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from ..score.buckets import duration_bucket
from .dataset import GroundTruth


@dataclass(frozen=True)
class CalibrationSummary:
    n: int
    bucket_accuracy: float
    log_elapsed_mae: float
    top1_pattern_accuracy: float | None
    top2_pattern_accuracy: float | None


def calibration_summary(
    predictions: list[tuple[GroundTruth, float, tuple[str, ...]]],
) -> CalibrationSummary:
    """`predictions` is a list of (gt, predicted_elapsed_s, ranked_patterns)."""
    if not predictions:
        return CalibrationSummary(0, 0.0, 0.0, None, None)

    bucket_hits = 0
    log_err_sum = 0.0
    top1_total = 0
    top1_hits = 0
    top2_hits = 0

    for gt, pred_s, ranked in predictions:
        if duration_bucket(pred_s) == duration_bucket(gt.elapsed_s):
            bucket_hits += 1
        log_err_sum += abs(math.log(max(pred_s, 1e-3)) - math.log(max(gt.elapsed_s, 1e-3)))
        if gt.ground_truth_pattern is not None and ranked:
            top1_total += 1
            if ranked[0] == gt.ground_truth_pattern:
                top1_hits += 1
            if gt.ground_truth_pattern in ranked[:2]:
                top2_hits += 1

    n = len(predictions)
    top1 = (top1_hits / top1_total) if top1_total else None
    top2 = (top2_hits / top1_total) if top1_total else None
    return CalibrationSummary(
        n=n,
        bucket_accuracy=bucket_hits / n,
        log_elapsed_mae=log_err_sum / n,
        top1_pattern_accuracy=top1,
        top2_pattern_accuracy=top2,
    )
