from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class FunctionFeatures:
    """Per-function static features extracted by the tree-sitter pass."""

    name: str
    start_line: int
    end_line: int
    body: str
    loc: int
    method_chain_calls: int
    iterator_combinators: int
    as_casts: int
    compound_assigns: int
    trait_method_calls: int
    unary_negations: int
    tuple_field_accesses: int
    const_items: int
    struct_literals: int

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("body", None)
        return d


@dataclass(frozen=True)
class StaticFeatures:
    """File-level container for per-function features plus the original source."""

    path: str
    source: str
    functions: tuple[FunctionFeatures, ...]

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "functions": [f.to_dict() for f in self.functions],
        }
