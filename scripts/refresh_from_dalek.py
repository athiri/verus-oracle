"""Re-vendor router/specialist prompts and patterns.py from inference-dalek.

Usage:
    python scripts/refresh_from_dalek.py [--dalek-root PATH]

Defaults to `~/Desktop/inference-dalek`.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

DEFAULT_DALEK_ROOT = Path.home() / "Desktop" / "inference-dalek"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dalek-root",
        type=Path,
        default=DEFAULT_DALEK_ROOT,
        help="Path to the inference-dalek checkout.",
    )
    args = parser.parse_args()

    src_prompts = args.dalek_root / "inference_dalek" / "rewrites" / "prompts"
    src_patterns = args.dalek_root / "inference_dalek" / "rewrites" / "patterns.py"
    if not src_prompts.is_dir() or not src_patterns.is_file():
        print(f"error: missing sources under {args.dalek_root}", file=sys.stderr)
        return 1

    here = Path(__file__).resolve().parent.parent
    dst_prompts = here / "verus_oracle" / "taxonomy" / "prompts"
    dst_patterns = here / "verus_oracle" / "taxonomy" / "patterns.py"

    dst_prompts.mkdir(parents=True, exist_ok=True)
    for f in src_prompts.glob("*.md"):
        shutil.copy2(f, dst_prompts / f.name)
        print(f"copied {f.name}")

    shutil.copy2(src_patterns, dst_patterns)
    print(f"copied patterns.py -> {dst_patterns}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
