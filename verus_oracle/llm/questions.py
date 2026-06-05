"""Per-category yes/no probes that refine the router's pattern call.

Each pattern has a small bank of questions whose answers shift the predicted
difficulty. The probe LLM call is one request per function (top pattern only),
backed by the cached specialist prompt for that pattern.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Mapping

from ..taxonomy import load_pattern_prompt
from .client import LLMClient


@dataclass(frozen=True)
class Question:
    qid: str
    text: str
    delta_if_yes: float


@dataclass(frozen=True)
class ProbeAnswer:
    qid: str
    text: str
    answer: bool
    delta: float


# qid is namespaced by pattern; delta is the difficulty shift added when answer=yes.
PROBES_BY_PATTERN: Mapping[str, tuple[Question, ...]] = {
    "R1": (
        Question("R1.loop", "Is the trait method call inside a loop body?", 0.5),
        Question("R1.transitive", "Is the trait method invoked on a transitively-accessed field (e.g. self.a.b.ct_eq)?", 0.3),
        Question("R1.unproven_helper", "Does the call site rely on a helper lemma that is not yet proven?", 0.5),
    ),
    "R2": (
        Question("R2.mixed", "Does the chain mix iterator combinators with arithmetic operators?", 0.5),
        Question("R2.deep", "Is the method chain depth strictly greater than 3?", 0.3),
    ),
    "R3": (
        Question("R3.closed_mut", "Does the iterator combinator close over mutable state?", 0.8),
        Question("R3.dynamic_count", "Does the iteration use filter/take_while/skip_while (so element count is data-dependent)?", 0.5),
        Question("R3.unknown_len", "Is the iteration over a slice whose length is not a compile-time constant?", 0.3),
    ),
    "R4": (
        Question("R4.heap", "Does the std/macro invocation involve heap allocation (Box::new, vec!, Vec::with_capacity)?", 0.5),
        Question("R4.conditional", "Does the std/macro call sit inside a conditional branch?", 0.2),
    ),
    "R5": (
        Question("R5.no_wrapper", "Is the unary negation on a user-defined type that lacks an existing wrapper helper?", 0.4),
    ),
    "R7": (
        Question("R7.lifetime", "Does the cast or reborrow change the referenced lifetime?", 0.6),
        Question("R7.in_arith", "Is the reborrow consumed by an arithmetic expression?", 0.4),
    ),
    "R8": (
        Question("R8.bounded_int", "Is the operand a fixed-width unsigned integer (u64/u32) subject to overflow checks?", 0.3),
        Question("R8.in_loop", "Is the arithmetic in a loop whose invariant must track the value?", 0.5),
    ),
    "R9": (
        Question("R9.multi_nonconst", "Does the const initializer call more than one non-const function?", 0.5),
        Question("R9.spec_use", "Does the const value appear later in a spec/proof expression?", 0.3),
    ),
    "R10": (
        Question("R10.spread", "Are the tuple field accesses spread across multiple call sites?", 0.2),
    ),
    "R11": (
        Question("R11.nontrivial_init", "Does any field initializer call a non-trivial function (more than a literal or field copy)?", 0.3),
    ),
}


def _build_schema(questions: tuple[Question, ...]) -> dict:
    return {
        "type": "object",
        "properties": {
            "answers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "qid": {"type": "string", "enum": [q.qid for q in questions]},
                        "answer": {"type": "boolean"},
                    },
                    "required": ["qid", "answer"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["answers"],
        "additionalProperties": False,
    }


def _build_system(pattern: str, questions: tuple[Question, ...]) -> str:
    base = load_pattern_prompt(pattern)
    appendix = [
        "",
        "## Probe questions",
        "",
        f"You will be shown a Rust snippet that the router classified as **{pattern}**.",
        "Answer each question below with a strict boolean. Return `true` only when you are",
        "confident the condition holds for this specific snippet.",
        "",
    ]
    for q in questions:
        appendix.append(f"- `{q.qid}`: {q.text}")
    return base + "\n".join(appendix)


def probe_pattern(
    pattern: str,
    snippet: str,
    client: LLMClient,
) -> tuple[ProbeAnswer, ...]:
    """One LLM call per function for the top pattern. Empty when no probes exist."""
    questions = PROBES_BY_PATTERN.get(pattern, ())
    if not questions:
        return ()

    response = client.call(
        system=_build_system(pattern, questions),
        user=snippet,
        max_tokens=512,
        output_schema=_build_schema(questions),
    )
    payload = json.loads(response.text)
    by_qid = {a["qid"]: bool(a["answer"]) for a in payload.get("answers", [])}

    return tuple(
        ProbeAnswer(
            qid=q.qid,
            text=q.text,
            answer=by_qid.get(q.qid, False),
            delta=q.delta_if_yes if by_qid.get(q.qid, False) else 0.0,
        )
        for q in questions
    )


def difficulty_delta(probes: tuple[ProbeAnswer, ...]) -> float:
    return sum(p.delta for p in probes)
