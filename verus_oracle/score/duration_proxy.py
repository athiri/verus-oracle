from __future__ import annotations

import json
import math
from pathlib import Path

from ..features import FunctionFeatures

# Default coefficients (used until `data/duration_proxy.json` is built via
# `scripts/build_calibration.py`). Replaced at import time when that file exists.
_DEFAULT_COEFFS: dict[str, float] = {
    "intercept": 1.5,
    "difficulty": 0.55,
    "loc": 0.015,
    "iter_combinators": 0.20,
    "method_chains": 0.05,
}

# The regression is log-linear and was fit on a narrow band of small functions
# (wall_s 36-52s, loc <= 50). Without a cap, exp() extrapolates wildly past
# anything the model has ever observed. 1800s = 30 min is a reasonable upper
# bound for any one Verus verification attempt; beyond that you would time out
# and refactor regardless.
_DEFAULT_MAX_ELAPSED_S = 1800.0

_COEFS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "duration_proxy.json"


def _load_coefs() -> tuple[dict[str, float], float]:
    if not _COEFS_PATH.is_file():
        return dict(_DEFAULT_COEFFS), _DEFAULT_MAX_ELAPSED_S
    payload = json.loads(_COEFS_PATH.read_text())
    coefs = {
        "intercept": float(payload["intercept"]),
        "difficulty": float(payload["difficulty"]),
        "loc": float(payload["loc"]),
        "iter_combinators": float(payload["iter_combinators"]),
        "method_chains": float(payload["method_chains"]),
    }
    cap = float(payload.get("max_elapsed_s", _DEFAULT_MAX_ELAPSED_S))
    return coefs, cap


_COEFFS, _MAX_ELAPSED_S = _load_coefs()


def predict_elapsed_seconds(
    features: FunctionFeatures,
    top_pattern: str,
    difficulty: float,
) -> float:
    log_elapsed = (
        _COEFFS["intercept"]
        + _COEFFS["difficulty"] * difficulty
        + _COEFFS["loc"] * features.loc
        + _COEFFS["iter_combinators"] * features.iterator_combinators
        + _COEFFS["method_chains"] * features.method_chain_calls
    )
    return min(math.exp(log_elapsed), _MAX_ELAPSED_S)
