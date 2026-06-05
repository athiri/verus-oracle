from __future__ import annotations

from importlib import resources

_PROMPT_FILES = {
    "R1": "r1_trait_wrapper.md",
    "R2": "r2_chain_named.md",
    "R3": "r3_iter_loop.md",
    "R4": "r4_std_inline.md",
    "R5": "r5_negation.md",
    "R7": "r7_cast_reborrow.md",
    "R8": "r8_arith.md",
    "R9": "r9_const_materialize.md",
    "R10": "r10_tuple_named.md",
    "R11": "r11_constructor_named.md",
}


def load_router_prompt() -> str:
    return resources.files("verus_oracle.taxonomy.prompts").joinpath("router.md").read_text()


def load_pattern_prompt(pattern_id: str) -> str:
    filename = _PROMPT_FILES[pattern_id]
    return resources.files("verus_oracle.taxonomy.prompts").joinpath(filename).read_text()
