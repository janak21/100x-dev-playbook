# Benchmark Challenge: SplitFair

A settlement engine for shared expenses. Looks simple; is not. Every trap in it is a documented small-model weakness: floating-point money math, deterministic remainder rounding, exact-sum validation, debt simplification with a hard transfer bound, and a strict I/O contract. Correctness is machine-verified by `verify.py` — no judgment calls on the core score.

## The task prompt (paste verbatim, identically, to every configuration)

```
Build a command-line program called splitfair (any language; Python or Node preferred).

USAGE: <program> input.json output.json
- On success: write output.json, exit code 0.
- On any invalid input: write NOTHING, print a useful message to stderr, exit code 1.

INPUT (input.json):
{
  "participants": ["Alice", "Bob", "Chad"],
  "expenses": [
    {"payer": "Alice", "amount": "100.00", "split_type": "equal", "participants": ["Alice","Bob","Chad"]},
    {"payer": "Bob",   "amount": "99.99",  "split_type": "shares",  "shares":   {"Alice": 1, "Bob": 2, "Chad": 3}},
    {"payer": "Chad",  "amount": "10.00",  "split_type": "percent", "percents": {"Alice": "33.33", "Bob": "33.33", "Chad": "33.34"}},
    {"payer": "Alice", "amount": "50.00",  "split_type": "exact",   "amounts":  {"Bob": "20.00", "Chad": "30.00"}}
  ]
}

RULES:
1. ALL money arithmetic must be exact. No binary floating point errors may ever
   affect a result. Amounts have at most 2 decimal places; reject otherwise.
2. Convert to integer cents internally.
3. Share computation per expense:
   - equal: weight 1 per listed participant. shares: positive integer weights.
     percent: decimal weights that must sum to EXACTLY 100 (reject otherwise).
     exact: listed amounts must sum to EXACTLY the expense amount (reject otherwise).
   - For weighted types: raw share = total_cents * weight / total_weight.
     Take the floor of each raw share in cents, then distribute the remaining
     cents ONE per participant in ALPHABETICAL order of name.
4. The payer can appear in their own split (they owe their own share to themselves).
5. Balance per person = total cents they paid - total cents they owe.
6. Settlement: produce transfers that bring every balance to exactly zero, using
   AT MOST (number of participants - 1) transfers. Algorithm: repeatedly match
   the largest debtor with the largest creditor (break ties alphabetically),
   transfer min(debt, credit).
7. Reject: unknown participant names, non-positive amounts, empty participants
   list, duplicate participant names, malformed JSON, amounts with >2 decimals.

OUTPUT (output.json):
{
  "balances":  {"Alice": 1666, "Bob": -833, "Chad": -833},
  "transfers": [{"from": "Bob", "to": "Alice", "amount_cents": 833}, ...]
}
balances = final NET position before settlement, in integer cents
(positive = is owed money). transfers = the settlement plan.

Include automated tests with your solution. The program will be graded by an
adversarial test harness including error cases.
```

## Why small models fail this (do not show contestants)

Float arithmetic (`0.1 + 0.2` class bugs; `amount * 100` via float produces 9999.999...), remainder cents silently lost or double-counted, percent validation done with float equality, payer-in-own-split double counting, settlement loops that exceed N-1 transfers or leave 1-cent residue, exit codes ignored, output written even on invalid input, and alphabetical tie-breaks skipped (non-deterministic output).

## Protocol

Four configurations, same prompt, one session each, no steering:

| Config | Model | Skill |
|---|---|---|
| A | small (e.g. Haiku) | installed |
| B | small | none |
| C | frontier (e.g. Fable/Opus) | installed |
| D | frontier | none |

Rules for a fair run: fresh session and fresh empty directory per config; paste the identical prompt; if the model asks questions, reply exactly "Proceed with your stated assumptions."; do not correct or hint; stop when the model declares done (with-skill configs will say "done pending your review" — accept without further steering). Save each config's final files into `results/<config>/`.

## Grading (three layers, in order of weight)

### 1. Correctness — machine-verified, 9 points
Run each solution against the cases in `cases/`:

```bash
# valid cases (6): program must exit 0 and output must pass verification
<program> cases/t1_equal_remainder.json out.json   && python3 verify.py cases/t1_equal_remainder.json out.json
<program> cases/t2_weighted_shares.json out.json   && python3 verify.py cases/t2_weighted_shares.json out.json
<program> cases/t3_percent_rounding.json out.json  && python3 verify.py cases/t3_percent_rounding.json out.json
<program> cases/t4_circular_debts.json out.json    && python3 verify.py cases/t4_circular_debts.json out.json
<program> cases/t5_self_only.json out.json         && python3 verify.py cases/t5_self_only.json out.json
<program> cases/t6_float_trap.json out.json        && python3 verify.py cases/t6_float_trap.json out.json

# error cases (3): program must exit NON-zero and write no output (check: echo $?)
<program> cases/e1_percent_99.json out.json
<program> cases/e2_exact_mismatch.json out.json
<program> cases/e3_negative_amount.json out.json
```

1 point per case. `verify.py` recomputes the reference answer with exact decimal arithmetic and checks: balances match, transfers settle every balance to exactly zero, transfer count ≤ N-1, all transfers positive with valid names.

### 2. Process — 6 assertions from the transcript, 6 points
Same discipline assertions as the skill's benchmark: plan communicated before code; spec/assumptions written before code; incremental commits (or clearly incremental construction); tests exist AND cover error cases; trade-offs confessed; plain-language explanation given. 1 point each.

### 3. Blind quality judge — tiebreaker
Give two solutions (anonymized as "Solution 1/2", strip all model references) to a model that wrote NEITHER, with: "Review both for a maintainer: correctness risks, clarity, error handling, test quality. Pick the one you'd rather inherit and say why." Run each pairing twice with the order swapped (order bias is real). Only counts when correctness scores tie.

### Scorecard

| Config | Correctness /9 | Process /6 | Tokens | Wall time | Judge |
|---|---|---|---|---|---|
| A small+skill | | | | | |
| B small bare | | | | | |
| C frontier+skill | | | | | |
| D frontier bare | | | | | |

The hypotheses this tests: (1) skill lifts correctness, not just process, on a hard task; (2) A ≥ D — a scaffolded small model beating a bare frontier model on *correctness* would be a much stronger result than the process-only version you already measured; (3) where A fails, the transcript shows whether the scaffold was followed-but-execution-failed (model limit) or abandoned (skill limit — fix the skill).

One warning from your own EVALS.md: one run per config is a sample, not a rate. If a result surprises you, rerun that config before believing it.
