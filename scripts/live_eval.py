"""Live router evaluation against the full v2 benchmark.

Loads ANTHROPIC_API_KEY from inference-dalek/.env, runs the router on every
case in `benchmarks/rewrites_v2.jsonl`, and reports top-1/top-2 accuracy
overall and per pattern. Predictions are written to
`data/live_router_predictions.jsonl` so re-runs can resume by case_id.

Usage:
  python scripts/live_eval.py [--dalek-root PATH] [--limit N] [--resume]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path


def _load_env(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dalek-root",
        type=Path,
        default=Path.home() / "Desktop" / "inference-dalek",
    )
    parser.add_argument("--limit", type=int, default=None, help="cap N cases (for smoke test)")
    parser.add_argument("--resume", action="store_true", help="skip case_ids already in the output file")
    parser.add_argument("--only-pattern", default=None, help="restrict to a single ground-truth pattern (e.g. R4)")
    parser.add_argument("--output", default=None, help="output JSONL path (default: data/live_router_predictions.jsonl)")
    args = parser.parse_args()

    _load_env(args.dalek_root / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("error: ANTHROPIC_API_KEY missing", file=sys.stderr)
        return 1

    from verus_oracle.llm import LLMClient, classify

    bench_path = args.dalek_root / "benchmarks" / "rewrites_v2.jsonl"
    cases = []
    for line in bench_path.read_text().splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        if d.get("original_code", "").strip():
            cases.append(d)
    if args.only_pattern:
        cases = [c for c in cases if c["pattern_id"] == args.only_pattern]
    if args.limit:
        cases = cases[: args.limit]

    default_out = "data/live_router_predictions.jsonl"
    out_path = Path(__file__).resolve().parent.parent / (args.output or default_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    done: set[str] = set()
    if args.resume and out_path.is_file():
        for line in out_path.read_text().splitlines():
            if line.strip():
                done.add(json.loads(line)["case_id"])

    client = LLMClient()
    fh = out_path.open("a")

    cache_read_total = 0
    cache_create_total = 0
    elapsed_total = 0.0
    n_done = 0

    for i, case in enumerate(cases):
        cid = case["id"]
        if cid in done:
            continue
        gt = case["pattern_id"]
        code = case["original_code"]
        t0 = time.time()
        try:
            ranked = classify(code, client)
        except Exception as e:
            print(f"[{i+1}/{len(cases)}] {cid} ERROR: {e}", file=sys.stderr)
            continue
        elapsed = time.time() - t0
        elapsed_total += elapsed

        top = ranked[0] if ranked else None
        second = ranked[1] if len(ranked) > 1 else None
        match_top1 = top is not None and top.pattern == gt
        match_top2 = (top and top.pattern == gt) or (second and second.pattern == gt)

        rec = {
            "case_id": cid,
            "ground_truth": gt,
            "top_1": top.pattern if top else None,
            "top_1_conf": top.confidence if top else None,
            "top_2": second.pattern if second else None,
            "top_2_conf": second.confidence if second else None,
            "match_top1": bool(match_top1),
            "match_top2": bool(match_top2),
            "elapsed_s": round(elapsed, 2),
        }
        fh.write(json.dumps(rec) + "\n")
        fh.flush()
        n_done += 1

        mark = "+" if match_top1 else ("~" if match_top2 else "x")
        print(f"[{i+1}/{len(cases)}] {cid:<8} gt={gt:<4} top={rec['top_1']:<4} {mark} ({elapsed:.1f}s)")

    fh.close()

    # Aggregate over ALL records in the file (including resumed).
    all_recs = [json.loads(l) for l in out_path.read_text().splitlines() if l.strip()]
    if not all_recs:
        print("no predictions to report")
        return 0

    total = len(all_recs)
    top1 = sum(1 for r in all_recs if r["match_top1"])
    top2 = sum(1 for r in all_recs if r["match_top2"])
    per_pattern: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "top1": 0, "top2": 0})
    confusion: dict[tuple[str, str], int] = defaultdict(int)
    for r in all_recs:
        p = r["ground_truth"]
        per_pattern[p]["n"] += 1
        if r["match_top1"]:
            per_pattern[p]["top1"] += 1
        if r["match_top2"]:
            per_pattern[p]["top2"] += 1
        confusion[(p, r["top_1"] or "?")] += 1

    print()
    print(f"=== aggregate over {total} cases ===")
    print(f"top-1 accuracy: {top1}/{total} = {top1/total:.1%}")
    print(f"top-2 accuracy: {top2}/{total} = {top2/total:.1%}")
    print(f"avg latency:    {elapsed_total/max(n_done,1):.2f}s/call (this run, n_new={n_done})")
    print()
    print("per-pattern breakdown:")
    print(f"  {'gt':<5} {'n':>4}  {'top1':>10}  {'top2':>10}")
    for p in sorted(per_pattern.keys()):
        d = per_pattern[p]
        print(
            f"  {p:<5} {d['n']:>4}  "
            f"{d['top1']:>4}/{d['n']:<4} ({d['top1']/d['n']:.0%})  "
            f"{d['top2']:>4}/{d['n']:<4} ({d['top2']/d['n']:.0%})"
        )
    print()
    print("confusion (gt -> top_1) for mispredictions:")
    for (gt, pred), n in sorted(confusion.items()):
        if gt != pred:
            print(f"  {gt} -> {pred}: {n}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
