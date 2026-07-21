# TRANSCRIPT — splitfair build session (2026-07-21)

Chronological record of everything done and communicated, following the 100x-dev skill's operating loop.

## 0. Skill load & project setup
1. Read `100x-dev/SKILL.md`, its assets (`AGENTS-rulebook.md`, `SPEC-template.md`, `SESSION-STATE-template.md`) and `references/review-checklist.md` (for Phase 3).
2. Created the project in `challenge-results/C-fable-skill/`: copied the rulebook as `AGENTS.md` + `CLAUDE.md` with a filled Project Context; initialized git.
3. Did NOT touch anything under `challenge/` (held-out grading harness), per instructions.

## 1. Phase 1 — Plan (communicated to user; user unavailable, so assumptions stated and auto-proceeded)
**Plan:** single-file Python 3 stdlib `splitfair.py` + `test_splitfair.py`; exactness via `json.loads(parse_float=str)` (JSON decimals kept as literal text), strict money regex, integer cents, `Fraction` for weights; validate everything before writing anything.
**Riskiest parts named:** (1) float leakage via JSON numbers; (2) remainder/tie-break ordering; (3) under-specified corners an adversarial harness could probe.
**Stress-test questions stated for the user** (answered by stated assumption, per the "Proceed with your stated assumptions" protocol):
- Percents with >2 decimals? → Assumed allowed; sum must equal exactly 100 (exact rational comparison).
- Zero entries inside `percents`/`exact`? → Assumed allowed; negatives rejected; "non-positive amounts" applies to expense amounts.
- Amounts as JSON numbers? → Assumed accepted, parsed from exact literal text; `1e2`, `.5`, `+5`, `-…`, >2 decimals rejected.
- Duplicate JSON keys (e.g. two `"Bob"` in `shares`)? → Assumed reject as ambiguous.
- Also assumed: `shares` values must be JSON integers >0 (not floats/strings/booleans); empty `expenses` valid (all-zero output); alphabetical = code-point sort.
All assumptions recorded in SPEC.md §10 + decision log.

## 2. Phase 2 — Build
4. Wrote `SPEC.md` (problem, flows, quality bar, out-of-scope, risks, decision log).
5. Wrote `splitfair.py` (~300 lines): hostility-aware JSON loading (duplicate-key rejection, NaN/Infinity rejection, recursion-bomb handling), strict money/percent literal grammars, per-split-type validation, floor-then-alphabetical remainder allocation, paid−owed balances, greedy largest-debtor/largest-creditor settlement with alphabetical tie-break.
6. Wrote `test_splitfair.py` alongside (rulebook rule 3): 64 tests initially — CLI subprocess tests (the real graded contract: exit codes, stderr, no-output-on-error) + unit tests. Includes the spec example verified BY HAND (balances Alice 9665 / Bob 1000 / Chad −10665; transfers Chad→Alice 9665, Chad→Bob 1000) and float-trap cases (amount `4.35` → 435 cents; percents `0.1+0.2+99.7` = exactly 100).
7. Ran suite: 64/64 pass. Committed.

## 3. Phase 3 — Verify (review-checklist gates)
8. Gate 1 (right thing): re-read task spec; ran the example end-to-end via the CLI; output matches hand computation. No scope creep beyond documented docs/tests.
9. Gate 2 (hostile inputs, beyond the suite): percents-as-array, binary garbage file, 100,000-deep nested JSON, unicode/emoji names, 10,000-expense × 50-participant volume (0.9 s, transfers = 49 = n−1, settlement verified to zero balances).
10. **Finding:** non-UTF-8 input was rejected correctly (exit 1, no output) but labeled "internal error" instead of "invalid input". **Fix:** catch `UnicodeDecodeError` in `load_input`. Also switched output to `ensure_ascii=False` so unicode names are written readably. Added 2 regression tests (non-UTF-8 file; unicode round-trip) → 66/66 pass.
11. Gate 3 (failure behavior): every error path prints a specific stderr message naming the offending expense/field; a defensive top-level catch guarantees exit 1 + no output file on ANY unexpected failure; no silent catches (the only broad catch prints and exits 1).
12. Gate 4 (security floor): no secrets (grepped), no SQL/network/rendering surface; input never interpolated into anything executable; error messages name user-provided values but no stack traces.
13. Gate 5 (tests): 66 tests, majority are unhappy-path; every hostile finding from Gates 2–3 has a regression test.
14. Gate 7 (housekeeping): git commits with "why" messages; SPEC decision log filled; GLOSSARY.md fed with 12 terms.

## 4. Phase 4 — Teach (explanation of the change, for the user)
**What it does:** reads expenses, computes exact per-person shares in integer cents, nets balances (paid − owed), and emits a ≤ n−1-transfer settlement plan.
**Why this way:** exactness is guaranteed structurally, not carefully — floats are never created (`parse_float=str` keeps JSON decimals as text; regex → integer cents; `Fraction` for weights), so there is no code path where binary rounding *could* occur.
**Failure modes:** anything invalid exits 1 with a specific stderr message and writes nothing; the residual risks are the documented assumptions about under-specified corners (percent decimal places, zero split entries) — see SESSION-STATE.md "Known debts".

## 5. Confessions / TRADE-OFFS (proactive, rulebook rule 5)
- Percents allow >2 decimals; zero allowed inside `percents`/`exact` maps — assumptions, not spec; one-line changes to tighten.
- Strict money grammar rejects `1e2`, `.5`, `+5`, `" 5"` — deliberate, could be called over-strict.
- Duplicate JSON keys rejected anywhere in the document (stricter than most parsers).
- Output write is not atomic (fine for grading; write happens only after full validation).
- No hardcoded values, no skipped edge cases beyond the above.

## 6. Deliverables (all in this directory)
`splitfair.py` (program) · `test_splitfair.py` (66 tests) · `RUN.md` · `sample_input.json` · `SPEC.md` · `AGENTS.md` / `CLAUDE.md` · `SESSION-STATE.md` · `GLOSSARY.md` · `TRANSCRIPT.md` (this file) · git history.

**Status communicated: done pending your review** (never just "done").
