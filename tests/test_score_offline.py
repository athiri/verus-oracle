from verus_oracle.pipeline import score_source


SAMPLE = """
fn easy(a: u64) -> u64 { a + 1 }

fn hard(xs: &[u64]) -> u64 {
    xs.iter().map(|x| *x * 2).filter(|x| *x > 0).fold(0u64, |a, x| a + x)
}
"""


def test_offline_pipeline_returns_verdict():
    v = score_source(SAMPLE, offline=True)
    assert v.bucket in {"easy", "medium", "hard"}
    assert v.duration_bucket in {"easy", "medium", "hard"}
    assert [f.function for f in v.functions] == ["easy", "hard"]


def test_iterator_function_scores_higher():
    v = score_source(SAMPLE, offline=True)
    by_name = {f.function: f for f in v.functions}
    assert by_name["hard"].est_duration_s > by_name["easy"].est_duration_s
