# TRANSCRIPT — splitfair (D-fable-bare)

Chronological record of everything done and communicated for this task.

## 1. Read the task, planned, stated assumptions

The user is unavailable for back-and-forth, so I stated my open questions and
the assumptions I proceeded with:

**Questions I would have asked, and the assumptions used instead:**

1. *Are amounts always strings, or can they be JSON numbers?* — Assumed both
   are accepted. To keep arithmetic exact even for JSON number literals, the
   JSON parser is configured with `parse_float=str`, so the literal decimal
   text (never a binary float) is what gets validated and converted to cents.
   A JSON literal `1.005` is therefore correctly rejected (3 decimals), and
   `10.05` is correctly parsed as 1005 cents.
2. *Do percent weights obey the "max 2 decimals" money rule?* — Assumed no:
   that rule is about *amounts*. Percents are weights; any number of decimal
   places is allowed, but they must be non-negative and sum to EXACTLY 100,
   verified with exact rational arithmetic (`fractions.Fraction`).
3. *Can percents / exact amounts be zero?* — Assumed yes (only `shares` are
   explicitly required to be *positive* integers; rule 7's "non-positive
   amounts" is read as applying to expense amounts, which must be > 0).
   Negative values are rejected everywhere.
4. *Must every participant appear in the output balances?* — Assumed yes
   (matches the spec example); balances are emitted for all participants in
   input-list order, including zeros.
5. *Duplicate keys inside a JSON object (e.g. `"shares": {"Bob":1,"Bob":2}`)?*
   — Assumed reject: ambiguous input, detected via `object_pairs_hook`.
6. *Empty `expenses` list?* — Assumed valid (all balances 0, no transfers).
   Only an empty `participants` list is a specified rejection.
7. *Empty-string participant names?* — Assumed reject.

The user's standing reply "Proceed with your stated assumptions" applied.

## 2. Wrote `splitfair.py`

Design decisions, mapped to the rules:

- **Exact arithmetic (rules 1–2):** all money parsed from decimal text via
  regex `^\d+(\.\d{1,2})?$` straight to integer cents. `parse_float=str` and
  a `parse_constant` guard (rejects NaN/Infinity) ensure no binary float ever
  exists in the pipeline. Percent weights use `fractions.Fraction`.
- **Share computation (rule 3):** for equal/shares/percent, raw share =
  `total_cents * weight / total_weight` as an exact Fraction; each share is
  floored; the leftover cents (always < number of split members) are handed
  out one each to split members in alphabetical order of name. `exact`
  amounts are taken as-is after validating they sum to the expense amount.
- **Percent sum check:** exact Fraction sum must equal 100 or reject.
- **Payer in own split (rule 4):** naturally supported; payer needn't be in
  the split either (spec's own 4th example expense).
- **Balances (rule 5):** cents paid minus cents owed, per participant.
- **Settlement (rule 6):** loop — pick the debtor with the largest debt and
  the creditor with the largest credit (ties broken by alphabetically first
  name), transfer `min(debt, credit)`. Each transfer zeroes at least one
  side, so the count is at most (nonzero balances − 1) ≤ (participants − 1).
- **Rejections (rule 7 + hardening):** malformed JSON, non-object top level,
  missing/invalid `participants` or `expenses`, empty or duplicate
  participants, non-string names, unknown payer or split member, unknown or
  missing `split_type`, non-positive / >2-decimal / malformed amounts
  (including `"1e2"`, `"1."`, `".5"`, `"-1"`, `NaN`, null, booleans),
  non-positive-integer share weights, percents not summing to exactly 100,
  exact amounts not summing to the total, empty split specs, duplicate JSON
  keys, wrong CLI argument count, unreadable input file.
- **Error contract:** the output file is opened only after every validation
  and computation has succeeded, so nothing is ever written on invalid
  input; errors go to stderr; exit code 1. Success: output written, exit 0.

Hand-verified the spec example: balances Alice 9665, Bob 1000, Chad −10665;
transfers Chad→Alice 9665, Chad→Bob 1000 (2 ≤ 3−1). (The literal numbers in
the task's OUTPUT sketch were illustrative and don't correspond to the four
example expenses; my hand computation follows the stated rules exactly.)

## 3. Wrote `test_splitfair.py` and ran it

39 unittest tests, mixing end-to-end CLI runs (subprocess, temp dirs) with
unit tests of `weighted_shares`, `settle`, and `parse_amount_cents`:

- worked example end-to-end, empty expenses list
- float traps ("0.30"/3, JSON literal `10.05`, huge amounts), integer amounts
- floor + alphabetical remainder distribution (1 and 2 leftover cents),
  shares 1:2:3 on 99.99, percent split, >2-decimal percents summing to 100
- settlement: largest-vs-largest matching, alphabetical tie-breaks, n−1 cap,
  transfers verifiably zero all balances
- rejection battery: every case asserts exit 1, non-empty stderr, and that
  the output file was NOT created — malformed JSON, missing file, wrong arg
  counts, empty/duplicate/non-string participants, missing keys, unknown
  names in every split type, 13 malformed amount strings, 3-decimal JSON
  number, negative/null amounts, percent sums ≠ 100, exact-sum mismatch,
  3-decimal exact amounts, 6 invalid share weights, empty split specs,
  duplicate name in equal split, unknown/missing split_type, non-object
  expense, duplicate JSON keys
- output shape: all participants present, all ints, transfer fields/positivity,
  payer inside their own split

Result: **39/39 pass** (`python3 test_splitfair.py`).

## 4. Manual end-to-end verification

- `python3 splitfair.py example_input.json example_output.json` → exit 0,
  output matches the hand computation (committed as `example_output.json`).
- Malformed-JSON run → stderr message, exit 1, confirmed no output file
  created (re-ran in a clean state to verify after a stale `/tmp` file gave
  a false alarm on the first check).

## 5. Deliverables (all in this directory)

- `splitfair.py` — the program (`python3 splitfair.py input.json output.json`)
- `test_splitfair.py` — automated tests (`python3 test_splitfair.py`)
- `example_input.json`, `example_output.json` — the spec example and its result
- `RUN.md` — run instructions and behavioral notes
- `TRANSCRIPT.md` — this file
