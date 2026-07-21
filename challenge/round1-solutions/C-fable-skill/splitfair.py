#!/usr/bin/env python3
"""splitfair — exact expense splitting and settlement.

Usage:
    python3 splitfair.py input.json output.json

On success: writes output.json and exits 0.
On any invalid input: writes nothing, prints a message to stderr, exits 1.

All money arithmetic is exact. JSON decimal literals are parsed as text
(never as binary floats), converted to integer cents, and weighted splits
use exact rational arithmetic (fractions.Fraction).
"""

import json
import math
import re
import sys
from fractions import Fraction

# A money literal: non-negative, plain decimal, at most 2 fraction digits.
# Rejects: sign characters, exponents (1e2), leading '.', trailing '.',
# whitespace, thousands separators, >2 decimals.
_MONEY_RE = re.compile(r"^[0-9]+(\.[0-9]{1,2})?$")

# A percent literal: non-negative plain decimal, any number of fraction digits.
_PERCENT_RE = re.compile(r"^[0-9]+(\.[0-9]+)?$")

_SPLIT_TYPES = ("equal", "shares", "percent", "exact")


class InputError(ValueError):
    """Any problem with the input that must cause exit code 1."""


# ---------------------------------------------------------------------------
# JSON loading (exactness- and hostility-aware)
# ---------------------------------------------------------------------------

def _reject_duplicate_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise InputError("duplicate key %r in a JSON object" % key)
        obj[key] = value
    return obj


def _reject_constant(name):
    raise InputError("non-finite JSON number %r is not allowed" % name)


def load_input(path):
    """Read and parse the input file.

    parse_float=str hands us the *exact literal text* of every JSON number
    that contains a '.' or exponent, so binary floating point never touches
    money values.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except UnicodeDecodeError as exc:
        raise InputError("input file is not valid UTF-8 text: %s" % exc) from exc
    except OSError as exc:
        raise InputError("cannot read input file: %s" % exc) from exc
    try:
        return json.loads(
            text,
            parse_float=str,
            parse_constant=_reject_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except InputError:
        raise
    except (ValueError, RecursionError) as exc:
        raise InputError("malformed JSON: %s" % exc) from exc


# ---------------------------------------------------------------------------
# Scalar parsing
# ---------------------------------------------------------------------------

def money_to_cents(value, context):
    """Parse a money value (JSON string or integer) into integer cents."""
    if type(value) is int:  # bool is an int subclass; 'type is' excludes it
        value = str(value)
    if not isinstance(value, str):
        raise InputError(
            "%s: money amount must be a string or integer, got %r"
            % (context, value)
        )
    if not _MONEY_RE.match(value):
        raise InputError(
            "%s: invalid money amount %r "
            "(must be a non-negative plain decimal with at most 2 decimal places)"
            % (context, value)
        )
    whole, _, frac = value.partition(".")
    return int(whole) * 100 + int(frac.ljust(2, "0")) if frac else int(whole) * 100


def percent_to_fraction(value, context):
    """Parse a percent weight (JSON string or integer) into an exact Fraction."""
    if type(value) is int:
        value = str(value)
    if not isinstance(value, str):
        raise InputError(
            "%s: percent must be a string or number, got %r" % (context, value)
        )
    if not _PERCENT_RE.match(value):
        raise InputError(
            "%s: invalid percent %r (must be a non-negative plain decimal)"
            % (context, value)
        )
    whole, _, frac = value.partition(".")
    result = Fraction(int(whole))
    if frac:
        result += Fraction(int(frac), 10 ** len(frac))
    return result


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _require(mapping, key, context):
    if not isinstance(mapping, dict):
        raise InputError("%s: expected a JSON object" % context)
    if key not in mapping:
        raise InputError("%s: missing required field %r" % (context, key))
    return mapping[key]


def _validate_participants(raw):
    if not isinstance(raw, list):
        raise InputError('"participants" must be a list')
    if not raw:
        raise InputError('"participants" must not be empty')
    seen = set()
    for name in raw:
        if not isinstance(name, str) or name == "":
            raise InputError(
                "participant names must be non-empty strings, got %r" % (name,)
            )
        if name in seen:
            raise InputError("duplicate participant name %r" % name)
        seen.add(name)
    return raw


def _validate_split_names(names, known, context):
    for name in names:
        if not isinstance(name, str):
            raise InputError("%s: participant name must be a string, got %r"
                             % (context, name))
        if name not in known:
            raise InputError("%s: unknown participant %r" % (context, name))


def _nonempty_dict(value, field, context):
    if not isinstance(value, dict):
        raise InputError("%s: %r must be a JSON object" % (context, field))
    if not value:
        raise InputError("%s: %r must not be empty" % (context, field))
    return value


# ---------------------------------------------------------------------------
# Share computation
# ---------------------------------------------------------------------------

def allocate(total_cents, weights):
    """Split total_cents by weight: floor each raw share, then hand the
    remaining cents out one each in alphabetical order of name."""
    total_weight = sum(weights.values())
    shares = {
        name: math.floor(Fraction(total_cents) * Fraction(weight) / total_weight)
        for name, weight in weights.items()
    }
    remainder = total_cents - sum(shares.values())
    for name in sorted(shares)[:remainder]:
        shares[name] += 1
    return shares


def expense_shares(expense, known, context):
    """Return {name: cents_owed} for one validated expense."""
    amount_cents = money_to_cents(_require(expense, "amount", context),
                                  "%s: \"amount\"" % context)
    if amount_cents <= 0:
        raise InputError("%s: amount must be positive" % context)

    split_type = _require(expense, "split_type", context)
    if split_type not in _SPLIT_TYPES:
        raise InputError(
            "%s: unknown split_type %r (expected one of %s)"
            % (context, split_type, ", ".join(_SPLIT_TYPES))
        )

    if split_type == "equal":
        listed = _require(expense, "participants", context)
        if not isinstance(listed, list) or not listed:
            raise InputError(
                '%s: "participants" must be a non-empty list' % context
            )
        _validate_split_names(listed, known, context)
        if len(set(listed)) != len(listed):
            raise InputError(
                '%s: duplicate name in expense "participants"' % context
            )
        return allocate(amount_cents, {name: 1 for name in listed})

    if split_type == "shares":
        shares = _nonempty_dict(_require(expense, "shares", context),
                                "shares", context)
        _validate_split_names(shares.keys(), known, context)
        for name, weight in shares.items():
            if type(weight) is not int or weight <= 0:
                raise InputError(
                    "%s: share for %r must be a positive integer, got %r"
                    % (context, name, weight)
                )
        return allocate(amount_cents, shares)

    if split_type == "percent":
        percents = _nonempty_dict(_require(expense, "percents", context),
                                  "percents", context)
        _validate_split_names(percents.keys(), known, context)
        weights = {
            name: percent_to_fraction(value, "%s: percent for %r" % (context, name))
            for name, value in percents.items()
        }
        total = sum(weights.values())
        if total != 100:
            raise InputError(
                "%s: percents must sum to exactly 100, got %s"
                % (context, format_fraction(total))
            )
        return allocate(amount_cents, weights)

    # split_type == "exact"
    amounts = _nonempty_dict(_require(expense, "amounts", context),
                             "amounts", context)
    _validate_split_names(amounts.keys(), known, context)
    cents = {
        name: money_to_cents(value, "%s: exact amount for %r" % (context, name))
        for name, value in amounts.items()
    }
    if sum(cents.values()) != amount_cents:
        raise InputError(
            "%s: exact amounts sum to %d cents but the expense amount is %d cents"
            % (context, sum(cents.values()), amount_cents)
        )
    return cents


def format_fraction(value):
    """Human-friendly rendering of a Fraction for error messages."""
    if value.denominator == 1:
        return str(value.numerator)
    return "%s (= %s)" % (value, float(value))


# ---------------------------------------------------------------------------
# Balances and settlement
# ---------------------------------------------------------------------------

def compute(data):
    if not isinstance(data, dict):
        raise InputError("top-level JSON value must be an object")
    participants = _validate_participants(_require(data, "participants", "input"))
    expenses = _require(data, "expenses", "input")
    if not isinstance(expenses, list):
        raise InputError('"expenses" must be a list')

    known = set(participants)
    paid = {name: 0 for name in participants}
    owed = {name: 0 for name in participants}

    for index, expense in enumerate(expenses):
        context = "expense #%d" % (index + 1)
        if not isinstance(expense, dict):
            raise InputError("%s: expected a JSON object" % context)
        payer = _require(expense, "payer", context)
        if not isinstance(payer, str) or payer not in known:
            raise InputError("%s: unknown payer %r" % (context, payer))
        shares = expense_shares(expense, known, context)
        paid[payer] += money_to_cents(expense["amount"], context)
        for name, cents in shares.items():
            owed[name] += cents

    balances = {name: paid[name] - owed[name] for name in participants}
    return {"balances": balances, "transfers": settle(balances)}


def settle(balances):
    """Greedy settlement: repeatedly match the largest debtor with the largest
    creditor (ties broken alphabetically), transfer min(debt, credit).
    Each transfer zeroes at least one party, so at most n-1 transfers occur."""
    debtors = {name: -bal for name, bal in balances.items() if bal < 0}
    creditors = {name: bal for name, bal in balances.items() if bal > 0}
    transfers = []
    while debtors:
        debtor = min(debtors, key=lambda n: (-debtors[n], n))
        creditor = min(creditors, key=lambda n: (-creditors[n], n))
        amount = min(debtors[debtor], creditors[creditor])
        transfers.append({"from": debtor, "to": creditor, "amount_cents": amount})
        debtors[debtor] -= amount
        creditors[creditor] -= amount
        if debtors[debtor] == 0:
            del debtors[debtor]
        if creditors[creditor] == 0:
            del creditors[creditor]
    # Invariant: balances sum to zero, so both sides empty together.
    assert not creditors, "settlement invariant violated"
    return transfers


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv):
    if len(argv) != 3:
        print("usage: python3 splitfair.py input.json output.json",
              file=sys.stderr)
        return 1
    try:
        result = compute(load_input(argv[1]))
    except InputError as exc:
        print("splitfair: invalid input: %s" % exc, file=sys.stderr)
        return 1
    except Exception as exc:  # defensive: never write output on any failure
        print("splitfair: internal error: %s" % exc, file=sys.stderr)
        return 1

    serialized = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    try:
        with open(argv[2], "w", encoding="utf-8") as fh:
            fh.write(serialized)
    except OSError as exc:
        print("splitfair: cannot write output file: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
