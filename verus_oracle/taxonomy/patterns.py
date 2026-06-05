"""The 10-pattern Verus rewrite taxonomy.

Vendored from inference-dalek/inference_dalek/rewrites/patterns.py.
Run `scripts/refresh_from_dalek.py` to re-sync after upstream changes.

The 10 in-scope patterns:

    R1   Trait method → wrapper                 (.ct_eq, .conditional_assign, .zeroize, ops)
    R2   Chain → named intermediates            (>=2 chained method calls)
    R3   Iterator → indexed loop                (.iter, .map, .fold, .zip, .collect, ...)
    R4   Std/macro → inline                     (Default::default, copy_from_slice, vec![..])
    R5   Negation/operator → wrapper            (unary -x on user types; !x.is_zero())
    R7   Cast / reborrow rewrite                (*self = (self as &T) + _rhs; `as &T`)
    R8   Arithmetic adaptation                  (+=, -=, *=, <<=, >>=; nested arithmetic)
    R9   Const → materialized                   (const FOO calling non-const fns)
    R10  Tuple-struct → named-field             (struct Foo(pub Inner); bare .0)
    R11  Constructor → named intermediates      (struct literal with complex init)

R6 (struct/visibility) and R12 ("other") are deliberately excluded; see upstream README.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class PatternMeta:
    """Runtime metadata for one rewrite pattern.

    Attributes
    ----------
    id
        Stable short tag (``"R1"`` … ``"R11"``).
    verify_meaningful
        ``True`` when standalone Verus verification carries real signal for this pattern.
        ``False`` for patterns whose proof obligations live in surrounding ``ensures`` /
        invariants (R2, R8, R10, R11); for these the oracle weights structural evidence
        more heavily.
    helper_imports
        Wrapper-function names typically used by the rewrite. Surfaces in the score
        report so a reader can spot a missing helper.
    """

    id: str
    verify_meaningful: bool
    helper_imports: tuple[str, ...] = ()


PATTERNS: tuple[PatternMeta, ...] = (
    PatternMeta(
        id="R1",
        verify_meaningful=True,
        helper_imports=(
            "conditional_assign_u64",
            "conditional_assign_field",
            "conditional_assign_scalar",
            "ct_eq_bytes32",
            "zeroize_bytes32",
            "zeroize_u64_array",
            "conditional_select_field",
            "conditional_negate_field",
        ),
    ),
    PatternMeta(id="R2", verify_meaningful=False),
    PatternMeta(id="R3", verify_meaningful=True),
    PatternMeta(
        id="R4",
        verify_meaningful=True,
        helper_imports=("write_range_wrapper", "copy_from_slice_wrapper"),
    ),
    PatternMeta(
        id="R5",
        verify_meaningful=True,
        helper_imports=(
            "negate_wrapper",
            "choice_not",
            "conditional_negate_field",
            "neg_field_inplace",
        ),
    ),
    PatternMeta(
        id="R7",
        verify_meaningful=True,
        helper_imports=("add_wrapper", "sub_wrapper", "mul_wrapper"),
    ),
    PatternMeta(id="R8", verify_meaningful=False),
    PatternMeta(id="R9", verify_meaningful=True),
    PatternMeta(id="R10", verify_meaningful=False),
    PatternMeta(id="R11", verify_meaningful=False),
)


PATTERN_IDS: tuple[str, ...] = tuple(p.id for p in PATTERNS)

_BY_ID: Mapping[str, PatternMeta] = {p.id: p for p in PATTERNS}


def get_pattern(pattern_id: str) -> PatternMeta:
    """Look up the :class:`PatternMeta` for *pattern_id*.

    Raises ``KeyError`` for unknown ids; silent fallthroughs here mask classifier bugs.
    """
    return _BY_ID[pattern_id]


__all__ = ["PATTERNS", "PATTERN_IDS", "PatternMeta", "get_pattern"]
