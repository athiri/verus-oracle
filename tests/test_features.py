from verus_oracle.features import extract_features


SAMPLE = """
fn add_chain(a: u64, b: u64) -> u64 {
    let z = (a + b).checked_add(1).unwrap();
    z
}

fn iter_sum(xs: &[u64]) -> u64 {
    xs.iter().map(|x| *x * 2).fold(0u64, |acc, x| acc + x)
}

fn conditional(a: &mut FieldElement, b: &FieldElement, c: Choice) {
    a.conditional_assign(b, c);
}

struct Wrap(pub u64);
fn tuple_access(w: Wrap) -> u64 { w.0 }
"""


def test_extract_finds_functions():
    sf = extract_features(SAMPLE)
    names = [f.name for f in sf.functions]
    assert names == ["add_chain", "iter_sum", "conditional", "tuple_access"]


def test_feature_counts():
    sf = extract_features(SAMPLE)
    by_name = {f.name: f for f in sf.functions}

    assert by_name["add_chain"].method_chain_calls >= 2
    assert by_name["iter_sum"].iterator_combinators >= 3
    assert by_name["conditional"].trait_method_calls == 1
    assert by_name["tuple_access"].tuple_field_accesses == 1
