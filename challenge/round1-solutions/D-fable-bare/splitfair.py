#!/usr/bin/env python3
"""splitfair: split shared expenses with exact integer-cent arithmetic.

Usage:
    python3 splitfair.py input.json output.json

On success: writes output.json and exits 0.
On any invalid input: writes nothing, prints a message to stderr, exits 1.

All money arithmetic is exact: amounts are parsed from their decimal text
representation straight into integer cents (binary floating point is never
allowed to influence a result; JSON number literals are intercepted as raw
strings), and percent weights are handled with exact rational arithmetic
(fractions.Fraction).
"""

import json
import re
import sys
from fractions import Fraction

SPLIT_TYPES = ("equal", "shares", "percent", "exact")

# Money amount: non-negative decimal with at most 2 decimal places.
AMOUNT_RE = re.compile(r"^\d+(\.\d{1,2})?$")
# Percent weight: non-negative decimal, any number of decimal places.
PERCENT_RE = re.compile(r"^\d+(\.\d+)?$")


class InputError(ValueError):
    """Any problem with the input that must cause exit code 1."""


# ---------------------------------------------------------------------------
# JSON loading (exactness-preserving)
# ---------------------------------------------------------------------------

def _reject_constant(text):
    raise InputError(f"invalid JSON number constant: {text}")


def _pairs_hook(pairs):
    d = {}
    for key, value in pairs:
        if key in d:
            raise InputError(f"duplicate key {key!r} in JSON object")
        d[key] = value
    return d


def load_input(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        raise InputError(f"cannot read input file {path!r}: {e}")
    except UnicodeDecodeError as e:
        raise InputError(f"input file {path!r} is not valid UTF-8: {e}")
    try:
        # parse_float=str keeps the literal decimal text so binary floating
        # point never touches any number in the input.
        return json.loads(
            text,
            parse_float=str,
            parse_constant=_reject_constant,
            object_pairs_hook=_pairs_hook,
        )
    except json.JSONDecodeError as e:
        raise InputError(f"malformed JSON in {path!r}: {e}")


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_amount_cents(value, ctx):
    """Parse a money amount (string like "12.34", or JSON integer) to cents.

    Rejects anything that is not a non-negative decimal with at most 2
    decimal places.
    """
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise InputError(f"{ctx}: amount must be a decimal string (or integer), got {value!r}")
    s = str(value)
    if not AMOUNT_RE.match(s):
        raise InputError(
            f"{ctx}: invalid amount {s!r} "
            f"(must be a non-negative decimal with at most 2 decimal places)"
        )
    if "." in s:
        whole, frac = s.split(".")
        frac = frac.ljust(2, "0")
    else:
        whole, frac = s, "00"
    return int(whole) * 100 + int(frac)


def parse_percent(value, ctx):
    """Parse a percent weight to an exact Fraction. Non-negative decimals only."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise InputError(f"{ctx}: percent must be a decimal string (or integer), got {value!r}")
    s = str(value)
    if not PERCENT_RE.match(s):
        raise InputError(f"{ctx}: invalid percent {s!r} (must be a non-negative decimal)")
    if "." in s:
        whole, frac = s.split(".")
        scale = 10 ** len(frac)
        return Fraction(int(whole) * scale + int(frac), scale)
    return Fraction(int(s))


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def weighted_shares(total_cents, weights, ctx):
    """Split total_cents by exact weights (dict name -> Fraction/int).

    raw share = total_cents * weight / total_weight; floor each raw share,
    then hand out the remaining cents one per participant in alphabetical
    order of name.
    """
    total_weight = sum(Fraction(w) for w in weights.values())
    if total_weight <= 0:
        raise InputError(f"{ctx}: total weight must be positive")
    shares = {}
    for name, w in weights.items():
        raw = Fraction(total_cents) * Fraction(w) / total_weight
        shares[name] = raw.numerator // raw.denominator  # exact floor
    remainder = total_cents - sum(shares.values())
    for name in sorted(shares)[:remainder]:
        shares[name] += 1
    return shares


def expense_shares(expense, participants, ctx):
    """Return dict name -> cents owed for one validated expense."""
    split_type = expense.get("split_type")
    if split_type not in SPLIT_TYPES:
        raise InputError(f"{ctx}: unknown split_type {split_type!r} "
                         f"(expected one of {', '.join(SPLIT_TYPES)})")

    total_cents = parse_amount_cents(expense.get("amount"), ctx)
    if total_cents <= 0:
        raise InputError(f"{ctx}: amount must be positive")

    payer = expense.get("payer")
    if not isinstance(payer, str):
        raise InputError(f"{ctx}: payer must be a string, got {payer!r}")
    if payer not in participants:
        raise InputError(f"{ctx}: unknown payer {payer!r}")

    if split_type == "equal":
        members = expense.get("participants")
        if not isinstance(members, list) or not members:
            raise InputError(f"{ctx}: 'equal' split requires a non-empty "
                             f"\"participants\" list")
        seen = set()
        for m in members:
            if not isinstance(m, str):
                raise InputError(f"{ctx}: participant names must be strings, got {m!r}")
            if m not in participants:
                raise InputError(f"{ctx}: unknown participant {m!r}")
            if m in seen:
                raise InputError(f"{ctx}: duplicate participant {m!r} in split")
            seen.add(m)
        return weighted_shares(total_cents, {m: 1 for m in members}, ctx)

    if split_type == "shares":
        shares = expense.get("shares")
        if not isinstance(shares, dict) or not shares:
            raise InputError(f"{ctx}: 'shares' split requires a non-empty "
                             f"\"shares\" object")
        for name, w in shares.items():
            if name not in participants:
                raise InputError(f"{ctx}: unknown participant {name!r} in shares")
            if isinstance(w, bool) or not isinstance(w, int) or w <= 0:
                raise InputError(f"{ctx}: share weight for {name!r} must be a "
                                 f"positive integer, got {w!r}")
        return weighted_shares(total_cents, shares, ctx)

    if split_type == "percent":
        percents = expense.get("percents")
        if not isinstance(percents, dict) or not percents:
            raise InputError(f"{ctx}: 'percent' split requires a non-empty "
                             f"\"percents\" object")
        weights = {}
        for name, p in percents.items():
            if name not in participants:
                raise InputError(f"{ctx}: unknown participant {name!r} in percents")
            weights[name] = parse_percent(p, f"{ctx} (percent for {name!r})")
        if sum(weights.values()) != Fraction(100):
            raise InputError(f"{ctx}: percents must sum to exactly 100")
        return weighted_shares(total_cents, weights, ctx)

    # split_type == "exact"
    amounts = expense.get("amounts")
    if not isinstance(amounts, dict) or not amounts:
        raise InputError(f"{ctx}: 'exact' split requires a non-empty "
                         f"\"amounts\" object")
    shares = {}
    for name, a in amounts.items():
        if name not in participants:
            raise InputError(f"{ctx}: unknown participant {name!r} in amounts")
        shares[name] = parse_amount_cents(a, f"{ctx} (amount for {name!r})")
    if sum(shares.values()) != total_cents:
        raise InputError(f"{ctx}: exact amounts must sum to exactly the "
                         f"expense amount")
    return shares


def compute_balances(data):
    """Validate the whole input; return (ordered participant list, balances)."""
    if not isinstance(data, dict):
        raise InputError("top-level JSON value must be an object")

    participants = data.get("participants")
    if not isinstance(participants, list) or not participants:
        raise InputError('"participants" must be a non-empty list of names')
    seen = set()
    for name in participants:
        if not isinstance(name, str) or name == "":
            raise InputError(f"participant names must be non-empty strings, got {name!r}")
        if name in seen:
            raise InputError(f"duplicate participant name {name!r}")
        seen.add(name)
    pset = set(participants)

    expenses = data.get("expenses")
    if not isinstance(expenses, list):
        raise InputError('"expenses" must be a list')

    paid = {name: 0 for name in participants}
    owed = {name: 0 for name in participants}
    for i, expense in enumerate(expenses):
        ctx = f"expense #{i + 1}"
        if not isinstance(expense, dict):
            raise InputError(f"{ctx}: each expense must be an object")
        shares = expense_shares(expense, pset, ctx)
        paid[expense["payer"]] += parse_amount_cents(expense["amount"], ctx)
        for name, cents in shares.items():
            owed[name] += cents

    balances = {name: paid[name] - owed[name] for name in participants}
    return participants, balances


def settle(balances):
    """Greedy settlement: repeatedly match the largest debtor with the largest
    creditor (ties broken alphabetically), transfer min(debt, credit).

    Produces at most (number of nonzero balances - 1) <= (participants - 1)
    transfers and brings every balance to exactly zero.
    """
    debtors = {n: -b for n, b in balances.items() if b < 0}
    creditors = {n: b for n, b in balances.items() if b > 0}
    transfers = []
    while debtors:
        debtor = min(debtors, key=lambda n: (-debtors[n], n))
        creditor = min(creditors, key=lambda n: (-creditors[n], n))
        t = min(debtors[debtor], creditors[creditor])
        transfers.append({"from": debtor, "to": creditor, "amount_cents": t})
        debtors[debtor] -= t
        creditors[creditor] -= t
        if debtors[debtor] == 0:
            del debtors[debtor]
        if creditors[creditor] == 0:
            del creditors[creditor]
    return transfers


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def run(input_path, output_path):
    data = load_input(input_path)
    participants, balances = compute_balances(data)
    transfers = settle(balances)
    result = {
        "balances": {name: balances[name] for name in participants},
        "transfers": transfers,
    }
    # Only opened for writing after everything above succeeded, so nothing is
    # ever written on invalid input.
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
            f.write("\n")
    except OSError as e:
        raise InputError(f"cannot write output file {output_path!r}: {e}")


def main(argv):
    if len(argv) != 3:
        print("usage: python3 splitfair.py input.json output.json", file=sys.stderr)
        return 1
    try:
        run(argv[1], argv[2])
    except InputError as e:
        print(f"splitfair: error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
