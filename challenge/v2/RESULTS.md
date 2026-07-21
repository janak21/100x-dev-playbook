# SplitFair v2 — Results

Run date: 2026-07-21. Same four configurations, one run each, identical under-specified
prompt, no steering. Skill configs used the **revised** SKILL.md (proportionality rule +
specific-confession rule + no duplicate scaffolding).

## Headline: the benchmark now discriminates

v1 scored 14/14 for everyone with byte-identical output. v2 produces a real spread.

| Config | Fairness /5 | Conservation /3 | Hostile /7 | Scale /1 | Determinism /1 | **Total /17** |
|---|---|---|---|---|---|---|
| C Fable+skill | 5 | 3 | 7 | 1 | 1 | **17** |
| D Fable bare | 5 | 3 | 7 | 1 | 1 | **17** |
| A Haiku+skill | 5 | 3 | 6 | 1 | 1 | **16** |
| B Haiku bare | **0** | 3 | 5 | 1 | 1 | **10** |

Scored out of 17, not 18: case `h8_empty_roster` was **withdrawn after the fact** because it
is not unambiguously invalid. C and D returned `{"balances":{},"transfers":[]}` with exit 0,
which is a defensible reading of an empty roster with no expenses. Charging that as an error
would have been my test's flaw scored against them. Withdrawing it costs C and D nothing
(both were otherwise perfect on hostile input) and is recorded here rather than silently applied.

## The decisive finding: B's inverted sign convention

The spec states "positive = is owed money." On `f1_thirds` — Ana pays $100.00 for three
people — the four configs produced:

```
A, C, D:  Ana +6666, Bob -3333, Cy -3333   transfers: Bob→Ana 3333, Cy→Ana 3333
B:        Ana -6666, Bob +3333, Cy +3333   transfers: Ana→Bob 3333, Ana→Cy 3333
```

B has the sign backwards, so **the person who paid for dinner is instructed to pay everyone
again**. This is the exact failure profile the whole system exists to catch: totals balance,
the settlement zeroes out, the JSON is well-formed, and the money flows the wrong way.

It survived because **B's own 15 tests all passed** — they encode the same misconception as
the implementation. Tests written from the code cannot catch a misreading of the spec; only
tests written from the spec can. B's v2 conservation cases passed too (3/3), because an
internally-consistent inversion still sums to zero. Only the fairness check, which compares
against an independently-derived proportional share, caught it.

## Bloat: the skill fix worked

`markdown lines ÷ python lines`, and file count, before and after the SKILL.md revision:

| Config | v1 ratio | v2 ratio | v1 files | v2 files |
|---|---|---|---|---|
| A Haiku+skill | 0.73 | **0.35** | 15 | 13 |
| C Fable+skill | 0.38 | **0.32** | 13 | 9 |
| B Haiku bare | 0.67 | 0.16 | 49 | 3 |
| D Fable bare | 0.24 | 0.16 | 8 | 4 |

The skill configs roughly halved their prose-to-code ratio, and v1's specific offenders are
gone: no DELIVERY-SUMMARY, no TECHNICAL-OVERVIEW, no self-graded compliance tables, and
`CLAUDE.md` is now a pointer rather than a byte-identical copy of `AGENTS.md`. Skill configs
still carry more prose than bare configs — that is the intended cost of SPEC/SESSION-STATE,
not theatre.

Confession quality also improved measurably. v1's skill run offered "no concurrency, no
persistence"; v2's offered "no Unicode normalization of names, so NFC and NFD spellings of
'José' are two participants that both appear in balances with nonzero amounts; untested and
unhandled" — a location and a consequence, which is what the revised rule demands.

## Blind tie-break (C vs D, both 17/17)

Anonymized as X/Y with a sealed key, order swapped:

| Order | Winner |
|---|---|
| X first | Y |
| Y first | Y |

**Y = C (Fable + skill), winning in both orders** — no order bias this time, unlike every
skill-effect pairing in v1. Both judges independently cited the same substantive reason:
C writes output atomically (`tempfile.mkstemp` + `os.replace`) so a crash mid-write cannot
leave a corrupt file, while D writes directly. One judge noted D had ~double the test count
and better type hints but held that it "doesn't offset failing the atomic-write requirement."

## What this run supports, and what it doesn't

**Supported:**
- The skill lifts a small model materially on a task requiring judgment: 16 vs 10, and the
  entire gap is judgment-shaped (fairness semantics and hostile-input handling), not syntax.
- The skill's edge on a frontier model is narrow but real and order-stable (atomic writes).
- The proportionality fix worked without degrading correctness — C scored top while cutting
  files from 13 to 9.

**Not supported:**
- "Small + skill beats frontier bare." It did not: A scored 16, D scored 17. v1's claim to
  the contrary came from process assertions the skill itself defines. On independent
  correctness the model gap persists — the skill narrows it, it does not erase it.

**Threats to validity:** n=1 per configuration; judges were Haiku models; `h8` was withdrawn
post hoc (disclosed above); round-2 hostile cases were authored by the same person who wrote
the skill, though they test spec properties rather than skill behaviour, and both bare
configs passed 7/7 of them.

## Remaining defects found in the winners

- **A (Haiku+skill)** accepts `"10.005"` and silently truncates it to 500 cents — sub-cent
  precision lost with no error. Its own tests missed it.
- **C and D** treat an empty roster as valid; defensible, but neither flagged the ambiguity
  in its assumptions.
