# Skill v1.1 — improvements and test results

Five changes, then tested. Every claim below is machine-measured.

## What changed in the skill

1. **Spec-derived test rule** (Phase 2). Tests must reach the expected answer by an
   independent route — an oracle (different arithmetic path, brute-force reference, or a
   hand-worked example) or a property (conservation, round-trip, bounds, idempotence).
   Tests that re-run the implementation and compare to its own output must be labelled
   smoke tests, not correctness tests. Motivated by v2's inverted-sign bug, which a full
   passing suite missed because the tests were written from the code.
2. **Input-contract pass** (Phase 3). For every accepted field, name and test the *nearest
   invalid neighbours*: precision, sign, size, type, and set boundaries. Motivated by the
   sub-cent truncation bug.
3. **Ceremony scaling** (new section). One-off script → no artifacts; feature → a spec
   section; new project → full setup. Stops the process from looking like bureaucracy on
   small work.
4. **`scripts/scaffold.sh`.** Deterministic setup (AGENTS.md, CLAUDE.md pointer, SPEC,
   SESSION-STATE, .gitignore, initial commit), idempotent, never overwrites.
5. **Resumability tested for the first time** (below).

## Test 1 — n=3, Haiku + skill v1.1, v2 harness

Fixing the n=1 problem for the config where the skill matters most.

| Run | Score | Fairness | Hostile | Bloat | Files |
|---|---|---|---|---|---|
| run1 | **17/17** | 5/5 | 7/7 | 0.15 | 6 |
| run2 | **17/17** | 5/5 | 7/7 | 0.52 | 14 |
| run3 | 16/17 | 5/5 | 6/7 | 0.42 | 6 |

Mean **16.7/17** vs **16/17** for skill v1.0 (n=1), and **10/17** for the bare small model.
The sub-cent bug (`"10.005"` silently truncated) is **fixed in 2 of 3 runs** — improved, not
eliminated. No run reproduced the sign-inversion failure; all three scored 5/5 on fairness.

**The most interesting correlation:** run3 is the only run whose test file contains no
oracle/independent-route language — and it is the only run that kept the bug. n=3, so this
is suggestive, not established, but it is the mechanism the rule predicts.

**Partial adoption, honestly:** all three used hand-calculated oracles (permitted by the
rule) but none used an independent arithmetic route such as `Fraction` — the strongest form.
Proportionality also slipped: run2 shipped 14 files at 0.52 bloat and run3 produced a
`DELIVERABLE_SUMMARY.txt`. The rule is being followed loosely, not tightly.

## Test 2 — resumability (first time ever tested)

A fresh session, a project it had never seen (the v2 Fable+skill solution, git history
removed), and a change request: add multi-currency support with a rates table, without
breaking anything.

What the session did: read SPEC.md, SESSION-STATE.md and AGENTS.md first, reported what they
told it (integer-cents invariant, Hamilton allocation, 78 existing tests, and that
multi-currency was explicitly listed OUT of scope — so the request changes the spec),
planned, then implemented 62 lines across three new and two modified functions.

Machine-verified results:

- **Regression: 16/16 on the original harness — zero regressions.** Fairness, conservation,
  all seven hostile cases, and determinism all still pass after the change.
- **New feature correct:** 100.00 EUR at rate 1.09 → 10900 base cents → Ana +5450, Bob −5450.
- Pre-existing 78 tests still pass; 17 new tests added.

This is the strongest single result in the whole exercise, because it tests the claim that
had never been tested: that the artifacts let a *different, fresh* session resume safely.
They did.

## Honest scorecard on the five improvements

| Improvement | Verdict |
|---|---|
| Spec-derived tests | Partially adopted; correlates with the bug fix; strongest form (independent arithmetic) not used |
| Input-contract pass | Works 2/3 runs |
| Ceremony scaling | Weakly followed — one run still over-produced |
| scaffold.sh | Works; tested for idempotence and for loud failure when git identity is unset |
| n=3 evidence | Done for one config only; the other three remain n=1 |

## Still open

- Trigger-description optimization (an unfired skill is worth zero) — not yet run.
- n=3 for the remaining three configurations.
- The proportionality and oracle rules need to bind harder; the current phrasing persuades
  but does not compel, and roughly a third of runs drift.
