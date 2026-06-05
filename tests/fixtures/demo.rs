// Demo input for verus-oracle.
//
// Four self-contained functions, each exercising a different rewrite pattern
// from the taxonomy (R1, R2, R3, R8). Run with:
//
//   verus-oracle tests/fixtures/demo.rs            # full LLM pipeline
//   verus-oracle tests/fixtures/demo.rs --offline  # static features only

trait ConstantTimeEq {
    fn ct_eq(&self, other: &Self) -> u8;
}

// R1: trait-method call that Verus wants wrapped.
fn is_equal<T: ConstantTimeEq>(a: &T, b: &T) -> bool {
    a.ct_eq(b) == 1
}

// R2: chained method calls that need to be named.
fn double_then_add(x: u64, y: u64) -> u64 {
    x.wrapping_mul(2).wrapping_add(y).wrapping_add(1)
}

// R3: iterator combinator chain that Verus prefers as a loop.
fn sum_squares(xs: &[u32]) -> u64 {
    xs.iter()
        .map(|x| (*x as u64) * (*x as u64))
        .filter(|s| *s < 1_000_000)
        .sum()
}

// R8: compound assignment + nested arithmetic.
fn pack_limb(carry: u64, low: u64) -> u128 {
    let mut acc: u128 = 0;
    acc += (carry as u128) << 51;
    acc += low as u128;
    acc
}
