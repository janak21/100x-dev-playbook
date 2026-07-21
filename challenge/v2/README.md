# SplitFair v2 — the non-saturating challenge

v1 saturated: all four configurations scored 14/14 with byte-identical output, because the
prompt dictated the algorithm and enumerated every rejection rule. The task was transcription.

v2 removes both. The prompt states **goals and invariants only** — no rounding rule, no
settlement algorithm, no list of what to reject. Contestants must exercise judgment, and
judgment is what actually varies between models and between disciplined and undisciplined work.

## The task prompt (paste verbatim to every configuration)

```
Build a command-line program called splitfair.

USAGE: python3 splitfair.py input.json output.json
- Success: write output.json, exit 0.
- Invalid input: write NOTHING, useful message to stderr, exit 1.

INPUT: a JSON object with "participants" (list of names) and "expenses". Each expense has
a "payer", an "amount" (a decimal string like "12.34"), a "split_type", and the data for
that split type:
  {"split_type":"equal",   "participants":["Ana","Bob"]}
  {"split_type":"shares",  "shares":{"Ana":1,"Bob":3}}
  {"split_type":"percent", "percents":{"Ana":"33.33","Bob":"66.67"}}
  {"split_type":"exact",   "amounts":{"Ana":"4.00","Bob":"8.34"}}

OUTPUT: {"balances": {"<name>": <int cents>, ...},
         "transfers": [{"from":"<name>","to":"<name>","amount_cents":<int>}, ...]}
balances = net position per person in integer cents, positive = is owed money.
transfers = a plan that settles everyone up.

REQUIREMENTS — these are the properties your program must satisfy. How you achieve them
is your decision; document the choices you make.
1. Money is never created or destroyed. Allocated shares must sum to exactly the expense
   amount, and balances must sum to exactly zero, in every case.
2. Splits must be fair to the cent: no participant's share may differ from their exact
   proportional share by a whole cent or more.
3. Settlement must use at most (number of participants - 1) transfers, all positive.
4. The program must be deterministic: the same input file must produce byte-identical
   output every run.
5. It must handle 50 participants and 5,000 expenses in under 10 seconds.
6. Invalid input must be rejected rather than silently mishandled. Decide what "invalid"
   means and defend it.

Include automated tests. An adversarial harness will grade this, including inputs designed
to break it.
```

Note what is absent versus v1: the remainder-distribution rule, the settlement algorithm,
the tie-break rule, and the enumerated rejection list. Requirement 6 in particular is the
main discriminator — v1 listed the seven things to reject, so every config rejected them.

## Scoring — 18 points, all machine-verified

**Fairness, 5 pts** (`verify2.py fairness`) — single-expense cases f1–f5. Checks shares sum
exactly to the total and every share is within 1 cent of the exact proportional value.
Algorithm-agnostic: any rounding scheme passes if it is fair.

**Conservation & settlement, 3 pts** (`verify2.py conserve`) — cases c1–c3. Balances sum to
zero, transfers settle everyone to exactly zero, positive amounts, within the n−1 bound.

**Hostile input, 8 pts** — cases h1–h8, none of which the prompt enumerates: duplicate name
in the roster, payer absent from the roster, unknown person in a split, amount with three
decimals, negative amount, percents summing to 99, exact amounts not matching the total,
empty roster. Each must exit non-zero **and** write no output file.

**Scale, 1 pt** — s1: 50 participants × 5,000 expenses must verify and finish under 10s.

**Determinism, 1 pt** — run c1 twice; output must be byte-identical.

## Secondary measure — bloat ratio (not scored, reported)

`markdown lines ÷ python lines`. v1's worst offender ran ~2:1 and was described by a blind
reviewer as "ceremony over substance". Reported alongside results because a benchmark that
only rewards output volume selects for exactly the failure mode this system exists to prevent.

## Bias controls

Same as v1, kept: identical prompt, no steering, contestants barred from reading this
directory, machine grading on layers that permit it, blind judging with a sealed key and
order-swapped pairings. v1 demonstrated why the last one matters — every skill-effect
pairing flipped with presentation order, so a single-order run would have produced a
confident and meaningless result.
