from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from .llm import DEFAULT_MODEL, LLMClient
from .pipeline import score_file


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--model", default=DEFAULT_MODEL, show_default=True, help="Anthropic model id.")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.option("--offline", is_flag=True, help="Skip all LLM calls (static features only).")
@click.option(
    "--no-probes",
    is_flag=True,
    help="Run the router but skip per-pattern yes/no probes (cheaper).",
)
def main(path: Path, model: str, as_json: bool, offline: bool, no_probes: bool) -> None:
    """Predict Verus verifiability for each function in a Rust file."""
    client = None if offline else LLMClient(model=model)
    verdict = score_file(
        path,
        client=client,
        offline=offline,
        use_probes=not no_probes,
    )

    if as_json:
        click.echo(json.dumps(verdict.to_dict(), indent=2))
        return

    click.echo(f"file: {verdict.file_path}")
    click.echo(
        f"  rollup: bucket={verdict.bucket}  "
        f"predicted={verdict.predicted_pattern}  "
        f"est={verdict.est_duration_s:.0f}s ({verdict.duration_bucket})"
    )
    if not verdict.functions:
        click.echo("  (no functions found)")
        return
    for fv in verdict.functions:
        click.echo(
            f"  {fv.function:<32} "
            f"bucket={fv.bucket:<6}  "
            f"top={fv.predicted_pattern}@{fv.top_confidence:.2f}  "
            f"est={fv.est_duration_s:.0f}s ({fv.duration_bucket})"
        )
        for p in fv.probes:
            mark = "Y" if p.answer else "N"
            click.echo(f"      [{mark}] {p.qid:<22} delta={p.delta:+.2f}")


if __name__ == "__main__":
    sys.exit(main())
