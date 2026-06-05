from __future__ import annotations

from pathlib import Path

import tree_sitter_rust
from tree_sitter import Language, Parser

from .schema import FunctionFeatures, StaticFeatures

_LANGUAGE = Language(tree_sitter_rust.language())
_PARSER = Parser(_LANGUAGE)

_ITER_COMBINATORS = frozenset({
    "iter", "iter_mut", "into_iter",
    "map", "filter", "fold", "collect",
    "zip", "enumerate", "rev", "chain",
    "skip", "take", "for_each", "sum", "product",
})

_TRAIT_METHODS = frozenset({
    "conditional_assign", "ct_eq", "zeroize",
    "conditional_select", "conditional_negate",
})


def extract_features(source: str, path: str = "<inline>") -> StaticFeatures:
    source_bytes = source.encode("utf-8")
    tree = _PARSER.parse(source_bytes)
    functions = tuple(_walk_functions(tree.root_node, source_bytes))
    return StaticFeatures(path=path, source=source, functions=functions)


def extract_from_path(path: str | Path) -> StaticFeatures:
    p = Path(path)
    return extract_features(p.read_text(), path=str(p))


def _walk_functions(root, source_bytes: bytes):
    for node in _iter_nodes(root):
        if node.type == "function_item":
            yield _features_for_function(node, source_bytes)


def _iter_nodes(node):
    yield node
    for child in node.children:
        yield from _iter_nodes(child)


def _text(node, source_bytes: bytes) -> str:
    return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _features_for_function(node, source_bytes: bytes) -> FunctionFeatures:
    name_node = node.child_by_field_name("name")
    body_node = node.child_by_field_name("body")
    name = _text(name_node, source_bytes) if name_node else "<anonymous>"
    body = _text(body_node, source_bytes) if body_node else ""
    start_line = node.start_point[0] + 1
    end_line = node.end_point[0] + 1
    loc = end_line - start_line + 1

    method_chain_calls = 0
    iterator_combinators = 0
    as_casts = 0
    compound_assigns = 0
    trait_method_calls = 0
    unary_negations = 0
    tuple_field_accesses = 0
    const_items = 0
    struct_literals = 0

    body_nodes = list(_iter_nodes(body_node)) if body_node else []

    for n in body_nodes:
        t = n.type
        if t == "call_expression":
            fn = n.child_by_field_name("function")
            if fn and fn.type == "field_expression":
                method_chain_calls += 1
                field = fn.child_by_field_name("field")
                if field is not None:
                    mname = _text(field, source_bytes)
                    if mname in _ITER_COMBINATORS:
                        iterator_combinators += 1
                    if mname in _TRAIT_METHODS:
                        trait_method_calls += 1
        elif t == "field_expression":
            field = n.child_by_field_name("field")
            if field is not None and _text(field, source_bytes).isdigit():
                tuple_field_accesses += 1
        elif t == "type_cast_expression":
            as_casts += 1
        elif t == "compound_assignment_expr":
            compound_assigns += 1
        elif t == "unary_expression":
            txt = _text(n, source_bytes).lstrip()
            if txt.startswith("-"):
                unary_negations += 1
        elif t == "const_item":
            const_items += 1
        elif t == "struct_expression":
            struct_literals += 1

    return FunctionFeatures(
        name=name,
        start_line=start_line,
        end_line=end_line,
        body=body,
        loc=loc,
        method_chain_calls=method_chain_calls,
        iterator_combinators=iterator_combinators,
        as_casts=as_casts,
        compound_assigns=compound_assigns,
        trait_method_calls=trait_method_calls,
        unary_negations=unary_negations,
        tuple_field_accesses=tuple_field_accesses,
        const_items=const_items,
        struct_literals=struct_literals,
    )
