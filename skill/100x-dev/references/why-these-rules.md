# Why these rules — the benchmark evidence

Every rule in SKILL.md earned its place by catching a real failure in controlled testing.
Read this when a rule seems arbitrary or expensive, or when the user asks why.

## The setup

Four configurations built the same program from the same prompt with no steering: a small
model and a frontier model, each with and without this skill. Correctness was graded by an
external harness (property-based, algorithm-agnostic), process by a blind grader, and
quality by blind reviewers with a sealed key and order-swapped pairings.

## Rule: tests must be derived from the spec, not the code

The small model without the skill produced a program that inverted the sign convention:
for "Ana pays $100 for three people" it output `Ana -6666, Bob +3333, Cy +3333` and a
transfer plan instructing **Ana to pay Bob and Cy** — the person who paid gets billed again.

It shipped because **its own 15 tests all passed.** They were written from the
implementation and inherited the same misreading. Conservation checks passed too, because
an internally consistent inversion still sums to zero. Only a check computed by an
independent route — comparing against a proportional share derived separately — caught it.

Score impact: 0/5 on fairness, 10/17 overall, versus 16–17/17 for every other configuration.

## Rule: input-contract pass (nearest invalid neighbours)

The small model *with* the skill accepted `"10.005"` and silently truncated it to 500 cents.
No error, no failing test, money lost. Nothing in the process caught it because nothing
required enumerating the values just outside each accepted set.

After the rule was added, this was fixed in 2 of 3 reruns. The one run that still failed was
also the only run whose tests contained no independent-route language — the two rules
reinforce each other.

## Rule: proportionality (prose must not outweigh code)

Blind reviewers, not knowing what produced what, described the skill's own early output as
"ceremony over substance — heavy classes and self-congratulatory docs while an actual
precision defect goes untested and undisclosed," at ~730 doc lines for 370 code lines, with
four static-method classes and dead code. A second config shipped `AGENTS.md` and
`CLAUDE.md` byte-identical.

After the rule: prose/code ratio fell 0.73 → 0.35 and 0.38 → 0.32; file counts fell 15 → 13
and 13 → 9; delivery summaries and compliance tables disappeared. Correctness did not
suffer — the leanest configuration scored top.

## Rule: confess with location and consequence

Before the rule, a confession list read "no concurrency, no persistence" — true of nearly
any small program, and it hid a real defect. After: "no Unicode normalization of names, so
NFC and NFD spellings of 'José' are two participants that both appear in balances with
nonzero amounts; untested and unhandled." One is filler; the other is actionable.

## Rule: artifacts exist so a different session can resume

Tested directly: a fresh session was given a project it had never seen, with git history
removed, and asked to add multi-currency support without breaking anything. It read
SESSION-STATE/SPEC/AGENTS, correctly reported that multi-currency was listed *out of scope*
(so the request changed the spec), and implemented the feature with **zero regressions** —
16/16 on the original harness, all 78 pre-existing tests still passing.

This is the only evidence that the artifacts pay for themselves; without it they are cost.

## Rule: scale the ceremony

The same testing showed the skill costs roughly +27% tokens and +50–85% wall time. On a
task the model already handles well, a bare frontier model was cheapest, fastest, and
scored 17/17. The skill's measurable edge there was one item (atomic writes). Therefore:
spend the ceremony where judgment is scarce, not uniformly.

## What the evidence does NOT support

An earlier round suggested "small model + skill beats frontier model bare." It did not
replicate under independent correctness grading: 16 vs 17. The skill **narrows** the model
gap on judgment-heavy work; it does not erase it. Claims in this file are n=1 to n=3 —
directional, not established. Per `evals.md`, that is a sample, not a rate.
