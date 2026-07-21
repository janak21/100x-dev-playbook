# Skill v1.2 → v1.4: token reduction, trigger check, and one honest negative result

## Token cost — what actually worked

| Lever | Effect | Evidence |
|---|---|---|
| **Ceremony scaling** (skip artifacts on small tasks) | **−36% tokens** | Small task (file-renamer) 41,905 tokens and 0/3 process artifacts, vs ~65,000 for full-project runs. The rule fired correctly and unprompted. |
| **Trimming SKILL.md** (2,798 → ~2,500 tokens) | ~−300 tokens per activation; **no measurable effect on run cost** | v1.1 mean 61,784 vs v1.2 mean 64,691 — within noise. The always-loaded body is a small fraction of a working session. |
| `scripts/scaffold.sh` | Setup is deterministic instead of regenerated | Tested for idempotence and for loud failure when git identity is missing |
| "Working economically" section | Unmeasured | Read-once-per-phase, batch tool calls, delete rather than append |

**The honest summary:** ceremony scaling is the real token lever, because it removes whole
artifacts rather than shaving instructions. Trimming the skill body looked attractive and
delivered almost nothing at the session level — worth doing for cleanliness, not for cost.

## Trigger accuracy

The automated optimizer could not run (the sandbox `claude` CLI is not logged in). Substitute:
two judges saw only the skill's name and description — never the body — and decided
YES/NO on 20 realistic queries, with the query order reversed for the second judge.

- Judge A: **20/20**. Judge B (order-reversed): **19/20**. Inter-judge agreement 19/20.
- The single disagreement: *"review this pull request from my contractor and tell me if the
  code quality is acceptable before i pay him."* Ground truth YES (the description names
  reviewing AI-generated code); Judge B said NO.

This approximates triggering rather than measuring it directly, so treat it as a sanity
check: the description is not obviously over- or under-triggering. Running the real
optimizer needs an authenticated CLI.

## The negative result: the sign-inversion bug is not fixed

Across three skill versions, n=3 / n=2 / n=3 on the identical task:

| Version | Scores | Inversion bug |
|---|---|---|
| v1.1 | 17, 17, 16 | 0 of 3 |
| v1.2 (trimmed) | 17, 11 | 1 of 2 |
| v1.3 (mechanical oracle rules) | 8, 17, 16 | 1 of 3 |

The v1.3 rules **did** increase compliance — all three runs contained
`test_worked_example_from_spec` and named oracle/property tests, versus 0–2 before. But
compliance did not prevent the failure. v1.3's run1 wrote the worked example *and* six
oracle/property tests and still inverted the convention: its balances said the payer owed
money while its transfers correctly paid the payer — internally contradictory, and its own
suite passed.

**Why the rule failed, mechanically:** a hand-computed worked example encodes whatever
reading you already hold. If the spec was misread, the hand calculation is confidently
wrong in the same direction. It locks the misreading in rather than exposing it.

**What v1.4 adds in response (UNTESTED):** a *semantic anchor test* — one assertion tying a
real-world situation to a specific sign, with the spec sentence quoted verbatim in a comment
(`# spec: "positive = is owed money"` / `assert balances["Ana"] > 0`). Verbatim quotation is
the point: paraphrasing is where the reading flips.

**This has not been tested.** It is a hypothesis with a mechanism, not a verified fix.
Testing it needs ~5 runs per version to distinguish a real effect from the noise visible
above — my n=2–3 samples cannot separate a 20% failure rate from a 33% one.

## Status

Ready for use, with a known limitation: on tasks with a signed or directional output
convention, roughly one run in three has inverted it across all versions tested. The
external harness catches it instantly; the model's own tests do not. Until the v1.4 anchor
rule is validated, treat any signed output as suspect and check one case by hand.
