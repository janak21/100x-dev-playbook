# SplitFair Challenge — Results (Round 1)

Run date: 2026-07-21. Four configurations, one run each, same prompt verbatim, no steering.
Contestants were barred from reading `challenge/` (held-out harness). Blind grading with a sealed key.

| Config | Model | Skill |
|---|---|---|
| A | Haiku 4.5 | installed |
| B | Haiku 4.5 | none |
| C | Fable 5 | installed |
| D | Fable 5 | none |

## Layer 1 — Correctness (machine-verified): NO DISCRIMINATION

| Config | Round 1 (9 cases) | Round 2 (5 harder cases) | Total |
|---|---|---|---|
| A Haiku+skill | 9/9 | 5/5 | **14/14** |
| B Haiku bare | 9/9 | 5/5 | **14/14** |
| C Fable+skill | 9/9 | 5/5 | **14/14** |
| D Fable bare | 9/9 | 5/5 | **14/14** |

Outputs were **byte-identical** across all four, including settlement tie-breaks and
remainder-cent ordering. Every config used exact arithmetic (`Decimal`/`Fraction`/
`parse_float=str`), correctly rejected all three invalid inputs with non-zero exit and
no output file.

**This is a failure of the challenge, not a finding about the models.** The prompt
specified the algorithm exactly — including remainder ordering and the settlement rule —
which removed the ambiguity that produces failure. A discriminating version must
under-specify and let the model choose (see "Round 2 design fixes" below).

The pre-registered prediction ("bare small model will likely fail the float trap and at
least one error case") was **wrong**.

## Layer 2 — Process discipline (blind grader, 6 assertions)

| Config | Score | Failed assertions |
|---|---|---|
| C Fable+skill | **6/6** | — |
| A Haiku+skill | **5/6** | trade-offs confessed (boilerplate only; a real precision defect went undisclosed) |
| D Fable bare | **4/6** | trade-offs confessed; plain-language explanation |
| B Haiku bare | **2/6** | plan-before-code; spec-first; incremental checkpoints; trade-offs |

Skill effect: **+3 on the small model, +2 on the frontier model.** Consistent with the
earlier benchmark: the skill reliably installs process discipline regardless of model.

## Layer 3 — Blind quality judging

Overall ranking by the blind grader: **C > D > A > B**.

Head-to-head, each pairing run twice with order swapped:

| Pairing | Order 1 | Order 2 | Verdict |
|---|---|---|---|
| D bare vs B bare (model effect, no skill) | D | D | **D wins, consistent** |
| C skill vs A skill (model effect, with skill) | C | C | **C wins, consistent** |
| A skill vs B bare (skill effect, small model) | B | A | **split — order bias** |
| C skill vs D bare (skill effect, frontier model) | C | D | **split — order bias** |

The **model** effect was robust to presentation order (4/4). The **skill** effect on
subjective code quality was **within judge noise** — in both split pairings the winner
tracked position, not substance. Without order-swapping this would have produced two
confident, meaningless results.

## Cost

| Config | Tokens | Wall time |
|---|---|---|
| A Haiku+skill | 74,900 | 514s |
| B Haiku bare | 58,836 | 367s |
| C Fable+skill | 77,505 | 550s |
| D Fable bare | 51,758 | 278s |

The skill costs roughly **+27% tokens and +50–85% wall time**. Bare frontier was the
cheapest and fastest config and still ranked 2nd on quality.

## Findings against the skill (recorded deliberately)

1. **The earlier "small+skill beats frontier-bare" result did NOT replicate.** On this
   task D (frontier, bare) outranked A (small, with skill) on quality. The prior result
   was measured on *process* assertions the skill itself defines; on independent quality
   judgment the model gap dominated.
2. **The skill induces documentation theatre on small models.** The blind grader
   described A as "ceremony over substance — heavy classes and self-congratulatory docs
   while an actual precision defect goes untested and undisclosed" (~730 doc lines for
   370 code lines, four static-method classes, dead code in the percent branch).
3. **The skill ships its own scaffolding as deliverables.** C shipped `AGENTS.md` and
   `CLAUDE.md` byte-identical; both skill configs shipped SESSION-STATE/SPEC files into
   the deliverable directory.
4. **Confession is the weakest enforced rule.** Only 1 of 4 configs produced a genuine
   limitations list; A produced boilerplate ("no concurrency, no persistence") while
   omitting a real defect.

## Threats to validity

- **n=1 per configuration.** Directional only. Per `EVALS.md`, this is a sample, not a rate.
- **Judges were Haiku models and one contestant was Haiku** (self-preference risk).
  Counter-evidence: Haiku judges ranked the two Haiku-produced solutions 3rd and 4th.
- **Assertions in Layer 2 encode the skill's own definition of good process**, authored
  by the same party that authored the skill. Layers 1 and 3 are independent of it.
- **Protocol deviation:** config B wrote its files to the wrong directory; files were
  recovered intact, but B ignored an explicit instruction, which is itself weak evidence
  about instruction-following.
- Round 2 cases were designed *after* seeing Round 1 saturate (exploratory, not
  pre-registered).

## Round 2 design fixes (for a discriminating rerun)

1. **Under-specify deliberately.** State the goal ("settle debts in as few transfers as
   possible; splits must be fair to the cent") and remove the prescribed algorithm,
   remainder rule, and tie-break rule. Score determinism and fairness invariants instead
   of an exact expected output.
2. **Add scale.** 50 participants, 5,000 expenses, a performance ceiling — forces
   algorithmic choices rather than transcription.
3. **Add a second session.** Hand back the finished repo with a change request
   ("multi-currency, with historical rates") in a fresh session. This tests
   SESSION-STATE.md and resumability, which nothing has yet exercised.
4. **Use a non-Claude judge if available**, and always keep order-swapping.
