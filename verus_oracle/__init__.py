"""verus-oracle: verifiability triage for Rust files targeting Verus."""

from .pipeline import score_source, score_file
from .features.schema import StaticFeatures
from .score.aggregate import Verdict

__all__ = ["score_source", "score_file", "StaticFeatures", "Verdict"]
__version__ = "0.1.0"
