"""Load BeneficialAI / dalek-lite ground-truth verification outcomes.

Expected JSONL schema (one record per function):

    {
        "id":            "<unique sample id>",
        "file":          "path/to/file.rs",
        "function":      "fn_name",
        "verified":      true,
        "elapsed_s":     12.4,
        "num_turns":     3,
        "level_reached": 2,
        "ground_truth_pattern": "R3"  // optional
    }

Source the records from this repo's `eval_runner` / HAB outputs. See
`inference_dalek/eval/types.py:RunReport` for the canonical fields.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GroundTruth:
    id: str
    file: str
    function: str
    verified: bool
    elapsed_s: float
    num_turns: int
    level_reached: int
    ground_truth_pattern: str | None = None


def load_jsonl(path: str | Path) -> tuple[GroundTruth, ...]:
    records = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        raw = json.loads(line)
        records.append(
            GroundTruth(
                id=raw["id"],
                file=raw["file"],
                function=raw["function"],
                verified=bool(raw["verified"]),
                elapsed_s=float(raw["elapsed_s"]),
                num_turns=int(raw["num_turns"]),
                level_reached=int(raw["level_reached"]),
                ground_truth_pattern=raw.get("ground_truth_pattern"),
            )
        )
    return tuple(records)
