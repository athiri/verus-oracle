"""Build calibration_seed.jsonl + fit duration_proxy.json from inference-dalek HAB output.

Joins:
  - `benchmarks/rewrites_v2.jsonl`              (case_id -> original_code, pattern_id)
  - `eval_results/.../reverify.jsonl`           (case_id -> live_wall_s, live_verifies)
  - `paper/calibration/examples_confirmation.jsonl`  (case_id -> wall_s)
  - `paper/calibration/skill_augment_results.jsonl`  (case_id -> new_wall_s)

Outputs:
  data/calibration_seed.jsonl  -- per-case records (features + ground truth)
  data/duration_proxy.json     -- fitted log-linear coefficients

Usage:
  python scripts/build_calibration.py --dalek-root ~/Desktop/inference-dalek
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np

from verus_oracle.features import extract_features

DEFAULT_DALEK_ROOT = Path.home() / "Desktop" / "inference-dalek"

_REVERIFY_PATHS = (
    "eval_results/intree_eval_repair_v6_wholecrate/reverify.jsonl",
)
_CONFIRMATION_PATH = "paper/calibration/examples_confirmation.jsonl"
_SKILL_AUGMENT_PATH = "paper/calibration/skill_augment_results.jsonl"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _build_benchmarks(dalek_root: Path) -> dict[str, dict]:
    raw = _read_jsonl(dalek_root / "benchmarks" / "rewrites_v2.jsonl")
    return {r["id"]: r for r in raw}


def _collect_wall_times(dalek_root: Path) -> dict[str, list[tuple[float, bool]]]:
    """case_id -> [(wall_s, verified), ...] aggregated across all sources."""
    out: dict[str, list[tuple[float, bool]]] = {}

    for rel in _REVERIFY_PATHS:
        for rec in _read_jsonl(dalek_root / rel):
            cid = rec.get("case_id")
            ws = rec.get("live_wall_s")
            ver = rec.get("live_verifies")
            if cid and ws is not None:
                out.setdefault(cid, []).append((float(ws), bool(ver)))

    for rec in _read_jsonl(dalek_root / _CONFIRMATION_PATH):
        cid = rec.get("case_id")
        ws = rec.get("wall_s")
        ver = rec.get("live_verifies")
        if cid and ws is not None:
            out.setdefault(cid, []).append((float(ws), bool(ver)))

    for rec in _read_jsonl(dalek_root / _SKILL_AUGMENT_PATH):
        cid = rec.get("case_id")
        ws = rec.get("new_wall_s")
        ver = rec.get("new_verifies")
        if cid and ws is not None:
            out.setdefault(cid, []).append((float(ws), bool(ver)))

    return out


def _pattern_difficulty(pattern: str) -> float:
    from verus_oracle.score.aggregate import _PATTERN_DIFFICULTY
    return _PATTERN_DIFFICULTY.get(pattern, 3.0)


def build_seed(dalek_root: Path, out_path: Path) -> list[dict]:
    bench = _build_benchmarks(dalek_root)
    walls = _collect_wall_times(dalek_root)

    records: list[dict] = []
    skipped_no_bench = 0
    skipped_no_function = 0

    for case_id, observations in walls.items():
        b = bench.get(case_id)
        if b is None:
            skipped_no_bench += 1
            continue
        source = b.get("original_code", "")
        if not source.strip():
            continue

        wrapped = source if source.lstrip().startswith("fn ") else f"fn _wrap() {{ {source} }}"
        sf = extract_features(wrapped)
        if not sf.functions:
            skipped_no_function += 1
            continue
        fn = sf.functions[0]

        verified_walls = [w for (w, v) in observations if v]
        any_wall = [w for (w, _) in observations]
        wall_s = float(np.median(verified_walls)) if verified_walls else float(np.median(any_wall))
        verified = bool(verified_walls)

        records.append({
            "case_id": case_id,
            "pattern": b.get("pattern_id"),
            "verified": verified,
            "wall_s": round(wall_s, 2),
            "n_observations": len(observations),
            "features": fn.to_dict(),
        })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    print(
        f"wrote {len(records)} records to {out_path}  "
        f"(skipped {skipped_no_bench} no-bench, {skipped_no_function} no-fn)"
    )
    return records


def fit_proxy(records: list[dict], out_path: Path) -> dict:
    """Closed-form log-linear fit on verified samples. Returns the fitted coefs."""
    rows = [r for r in records if r["verified"] and r["wall_s"] > 0]
    if len(rows) < 8:
        print(f"warning: only {len(rows)} verified samples; using defaults", file=sys.stderr)
        return {}

    X = []
    y = []
    for r in rows:
        f = r["features"]
        difficulty = _pattern_difficulty(r["pattern"])
        X.append([
            1.0,
            difficulty,
            f["loc"],
            f["iterator_combinators"],
            f["method_chain_calls"],
        ])
        y.append(math.log(r["wall_s"]))
    X = np.asarray(X)
    y = np.asarray(y)

    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    yhat = X @ beta
    resid = y - yhat
    rmse = float(np.sqrt((resid ** 2).mean()))
    r2 = 1.0 - float((resid ** 2).sum() / max(((y - y.mean()) ** 2).sum(), 1e-9))

    coefs = {
        "intercept": float(beta[0]),
        "difficulty": float(beta[1]),
        "loc": float(beta[2]),
        "iter_combinators": float(beta[3]),
        "method_chains": float(beta[4]),
        "n_samples": len(rows),
        "rmse_log_s": round(rmse, 3),
        "r2": round(r2, 3),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(coefs, indent=2))
    print(f"fit on n={len(rows)}  rmse(log_s)={rmse:.3f}  r2={r2:.3f}")
    print(f"  intercept={coefs['intercept']:+.3f}  difficulty={coefs['difficulty']:+.3f}  "
          f"loc={coefs['loc']:+.4f}  iter={coefs['iter_combinators']:+.3f}  "
          f"chains={coefs['method_chains']:+.4f}")
    print(f"  wrote {out_path}")
    return coefs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dalek-root", type=Path, default=DEFAULT_DALEK_ROOT)
    args = parser.parse_args()

    here = Path(__file__).resolve().parent.parent
    seed_path = here / "data" / "calibration_seed.jsonl"
    coefs_path = here / "data" / "duration_proxy.json"

    records = build_seed(args.dalek_root, seed_path)
    fit_proxy(records, coefs_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
