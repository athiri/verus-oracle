# Router prompt

You classify a short Rust snippet from `signal-curve25519-4.1.3` into
the rewrite pattern(s) needed to make it pass `cargo verus verify`
inside dalek-lite.

## In-scope patterns

| Id  | Pattern                          | Trigger                                                                 |
|-----|----------------------------------|-------------------------------------------------------------------------|
| R1  | Trait method → wrapper           | `.conditional_assign(`, `.ct_eq(`, `.zeroize(`, `.conditional_select(`, `.conditional_negate(`, operator overloads on user types |
| R2  | Chain → named intermediates      | Two or more chained method calls; compound expression that needs anchoring |
| R3  | Iterator → indexed loop          | Iterator combinators: `.iter()`, `.iter_mut()`, `.into_iter()`, iterator-`.map()`, `.fold()`, `.zip()`, `.collect()`, `.enumerate()`, `.rev()`. **Does NOT include `Result::map` / `Option::map`** — those are *not* iteration. |
| R4  | Std/macro / syntactic adaptation → inline | `Default::default()`, `.copy_from_slice(`, `Box::new(`, `vec![…]`; **also**: a closure binding (`let f = \|x\| { … };`), a nested `fn` defined inside another `fn`, `debug_assert!(…)` macros, array-literal buffer init (`let mut buf = [0u8; 32];`) that is the load-bearing Verus-blocker in the snippet. R4 is the "syntactic adaptation" bucket — pick it when the snippet's main verification obstacle is *Rust syntax Verus doesn't accept*, not deep proof structure. |
| R5  | Negation/operator → wrapper      | Unary `-x` on user types; `!x.is_zero()` style                         |
| R7  | Cast / reborrow rewrite          | `*self = (self as &T) + _rhs`; explicit `as &T` reborrows               |
| R8  | Arithmetic adaptation            | `+=` `-=` `*=` `<<=` `>>=`; deeply nested arithmetic that needs splitting |
| R9  | Const → materialized             | `const FOO: Foo = Foo { … }` calling non-const fns / trait impls        |
| R10 | Tuple-struct → named-field       | `struct Foo(pub Inner)` and bare `.0` accesses                          |
| R11 | Constructor → named intermediates| Struct-literal with non-trivial field initializers                      |

`R6` and `R12` are **out of scope** — never return them.

## Tie-breakers

- `*self = (self as &T) + _rhs` → top-1 = R7 (the reborrow is the
  load-bearing change; the assign chain is incidental).
- `acc.conditional_assign(&new_acc, choice_not(inputs[i].is_zero()))` →
  top-1 = R1, top-2 = R5.  Both are real edits.
- Iterator combinator + intermediate naming inside the loop body →
  top-1 = R3 alone (the loop conversion subsumes naming).
- Trait-method call inside a method-chain that's also being split →
  top-1 = R1, top-2 = R2.
- `bytes.try_into().map(TupleStruct)` (a `Result::map` whose closure is a
  tuple-struct constructor) → top-1 = R10 (the tuple-struct constructor is
  the load-bearing rewrite), top-2 = R3. `.map` on a `Result` / `Option` is
  *not* iteration — do not classify these as R3 on the `.map` alone.
- Function body that defines an inner `fn` (e.g. `fn m(x: u64, y: u64) -> u128 { … }`
  nested inside an outer `fn`) → top-1 = R4. Inner-fn definitions are a syntactic
  pattern Verus does not support and the lifting/inlining is the load-bearing edit,
  even when the body contains arithmetic (don't pick R8) or array literals.
- Function body that introduces a closure (`let load8 = |input: &[u8]| -> u64 { … };`)
  → top-1 = R4. The closure is the syntactic blocker; don't pick R10/R11 just because
  the surrounding code constructs a tuple-struct or named struct.
- `let mut buf = [0u8; N]; … Struct { field: buf }` (array-literal buffer init
  consumed by a struct literal) → top-1 = R4 (the array-init is the Verus-blocker
  the dalek-lite rewrites target), top-2 = R11.
- `Foo::a(&Foo::b(self))` (chained associated-function calls, *not* method calls)
  → top-1 = R2 only if the rewrite splits the chain; otherwise the snippet is
  R4-trivial and the verdict is the surrounding `ensures` annotation.

## Few-shot calibration

Snippet:
```rust
self.limbs[i].conditional_assign(&other.limbs[i], choice);
```
Output:
```json
{"ranked": [{"pattern": "R1", "confidence": 0.95}, {"pattern": "R2", "confidence": 0.10}]}
```

Snippet:
```rust
let z = (a + b).square().mul(&c);
```
Output:
```json
{"ranked": [{"pattern": "R2", "confidence": 0.85}, {"pattern": "R1", "confidence": 0.40}]}
```

Snippet:
```rust
let bytes: [u8; 32] = scalars.iter().map(|s| s.to_bytes()[0]).collect::<Vec<_>>().try_into().unwrap();
```
Output:
```json
{"ranked": [{"pattern": "R3", "confidence": 0.95}, {"pattern": "R2", "confidence": 0.30}]}
```

Snippet:
```rust
*self = (self as &EdwardsPoint) + _rhs;
```
Output:
```json
{"ranked": [{"pattern": "R7", "confidence": 0.90}, {"pattern": "R1", "confidence": 0.20}]}
```

Snippet:
```rust
let nx = -&x;
```
Output:
```json
{"ranked": [{"pattern": "R5", "confidence": 0.95}, {"pattern": "R1", "confidence": 0.10}]}
```

Snippet:
```rust
acc += a * b;
```
Output:
```json
{"ranked": [{"pattern": "R8", "confidence": 0.90}, {"pattern": "R2", "confidence": 0.25}]}
```

Snippet:
```rust
pub const ONE: FieldElement51 = FieldElement51::from_bytes(&[1, 0, 0, /* ... */]);
```
Output:
```json
{"ranked": [{"pattern": "R9", "confidence": 0.92}, {"pattern": "R4", "confidence": 0.20}]}
```

Snippet:
```rust
pub struct Scalar(pub [u8; 32]);
let s = Scalar(buf);
let b = s.0;
```
Output:
```json
{"ranked": [{"pattern": "R10", "confidence": 0.93}, {"pattern": "R11", "confidence": 0.30}]}
```

Snippet:
```rust
fn from(x: u8) -> Scalar {
    let mut s_bytes = [0u8; 32];
    s_bytes[0] = x;
    Scalar { bytes: s_bytes }
}
```
Output:
```json
{"ranked": [{"pattern": "R4", "confidence": 0.85}, {"pattern": "R11", "confidence": 0.30}]}
```

Snippet:
```rust
pub fn from_bytes(bytes: &[u8; 32]) -> FieldElement51 {
    let load8 = |input: &[u8]| -> u64 {
        (input[0] as u64) | ((input[1] as u64) << 8)
    };
    FieldElement51([load8(&bytes[0..]) & MASK])
}
```
Output:
```json
{"ranked": [{"pattern": "R4", "confidence": 0.88}, {"pattern": "R10", "confidence": 0.25}]}
```

Snippet:
```rust
fn mul(self, _rhs: &Foo) -> Foo {
    #[inline(always)]
    fn m(x: u64, y: u64) -> u128 { (x as u128) * (y as u128) }
    let a = &self.0;
    Foo([m(a[0], a[0])])
}
```
Output:
```json
{"ranked": [{"pattern": "R4", "confidence": 0.88}, {"pattern": "R8", "confidence": 0.30}]}
```

## Output protocol

Return **strict JSON** in exactly this shape — no Markdown, no fences,
no prose:

```
{"ranked": [{"pattern": "<R-id>", "confidence": <0.0-1.0>}, {"pattern": "<R-id>", "confidence": <0.0-1.0>}]}
```

Rules:

* Exactly two entries in `"ranked"`.
* `"pattern"` is one of `R1`, `R2`, `R3`, `R4`, `R5`, `R7`, `R8`, `R9`,
  `R10`, `R11` — never `R6` or `R12`.
* The two patterns must differ.
* Confidences are floats in `[0.0, 1.0]`, with the top-1 strictly
  greater-or-equal to the top-2.  These are calibrated probabilities,
  not arbitrary scores: a confidence of 0.95 means ≈95 % of similar
  snippets you'd label this pattern.
