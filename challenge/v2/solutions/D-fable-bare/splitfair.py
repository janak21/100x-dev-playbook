#!/usr/bin/env python3
"""splitfair -- fair expense splitting to the cent.

Usage:
    python3 splitfair.py input.json output.json

Reads an expense ledger, computes each participant's net balance in integer
cents, and emits a settlement plan using at most (n - 1) transfers.

Design notes live in README.md; the short version:

  * All money is integer cents internally.  Decimal strings are parsed with
    `decimal.Decimal` (never `float`) so no binary rounding error can occur.
  * Proportional splits use the largest-remainder (Hamilton) method on exact
    integer arithmetic, so allocations sum to the expense total exactly and
    every share is within one cent of the exact proportional value.
  * Ties in the remainder ranking are broken by the participant's index in
    the top-level "participants" list, which makes the result deterministic.
  * Settlement is a greedy two-pointer match of the largest creditor against
    the largest debtor; each step zeroes at least one party, so at most
    (n - 1) transfers are emitted and all of them are strictly positive.
"""

from __future__ import annotations

import json
import re
import sys
from decimal import Decimal, InvalidOperation

# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------


class InvalidInput(Exception):
    """Raised for any input we refuse to process.  Message goes to stderr."""


# A strict decimal-string grammar.  Deliberately rejects exponent notation
# ("1e2"), bare leading dots (".5"), underscores, whitespace padding, and the
# special values nan/inf -- all of which `Decimal()` would otherwise accept.
_DECIMAL_RE = re.compile(r"^-?\d+(\.\d+)?$")


def _fail(msg: str) -> "InvalidInput":
    return InvalidInput(msg)


# --------------------------------------------------------------------------
# JSON loading with duplicate-key and non-finite detection
# --------------------------------------------------------------------------


def _object_pairs_hook(pairs):
    """Reject duplicate keys instead of silently keeping the last one.

    `{"Ana": "1.00", "Ana": "2.00"}` is legal JSON but ambiguous money, and
    Python's default behaviour (last wins) would silently discard a value.
    """
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise _fail("duplicate JSON object key: %r" % (key,))
        seen[key] = value
    return seen


def _reject_constant(name):
    raise _fail("JSON contains non-finite number: %s" % name)


def load_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        raise _fail("cannot read input file %r: %s" % (path, exc.strerror or exc))
    except UnicodeDecodeError as exc:
        raise _fail("input file %r is not valid UTF-8: %s" % (path, exc))

    try:
        return json.loads(
            text,
            object_pairs_hook=_object_pairs_hook,
            parse_constant=_reject_constant,
        )
    except InvalidInput:
        raise
    except ValueError as exc:
        raise _fail("input file %r is not valid JSON: %s" % (path, exc))


# --------------------------------------------------------------------------
# Scalar parsing helpers
# --------------------------------------------------------------------------


def parse_decimal(value, where: str) -> Decimal:
    """Parse a JSON value that must be a decimal *string*.

    Numbers are rejected on purpose: JSON numbers are IEEE-754 doubles in
    almost every producer and consumer, so "0.1" and 0.1 are not the same
    quantity.  Money must arrive as text.
    """
    if isinstance(value, bool) or not isinstance(value, str):
        raise _fail("%s must be a decimal string, got %s" % (where, _typename(value)))
    if not _DECIMAL_RE.match(value):
        raise _fail("%s is not a well-formed decimal string: %r" % (where, value))
    try:
        return Decimal(value)
    except InvalidOperation:
        raise _fail("%s is not a valid decimal: %r" % (where, value))


def scaled_int(value: Decimal, places: int):
    """Return `value * 10**places` as an exact int, or None if not integral.

    Deliberately avoids Decimal arithmetic.  `decimal`'s default context has
    28 significant digits, so `Decimal("33.333...") * 100` would *round* on a
    long input -- exactly the kind of silent precision loss this program
    exists to prevent.  Working from the digit tuple is exact at any length.
    """
    sign, digits, exponent = value.as_tuple()
    if not isinstance(exponent, int):  # nan / inf, unreachable via our regex
        return None
    mantissa = 0
    for digit in digits:
        mantissa = mantissa * 10 + digit
    shift = exponent + places
    if shift >= 0:
        result = mantissa * (10 ** shift)
    else:
        divisor = 10 ** (-shift)
        if mantissa % divisor:
            return None
        result = mantissa // divisor
    return -result if sign else result


def to_cents(value: Decimal, where: str) -> int:
    """Convert a Decimal amount to integer cents, refusing sub-cent precision.

    We will not round sub-cent input: "10.005" is a data-entry bug or an
    attempt to smuggle in money that cannot be paid, and silently rounding it
    would violate the "money is never created or destroyed" contract at the
    boundary.
    """
    result = scaled_int(value, 2)
    if result is None:
        raise _fail(
            "%s has sub-cent precision and cannot be represented exactly: %s"
            % (where, value)
        )
    return result


def parse_weight(value, where: str) -> Decimal:
    """Parse a share weight: a non-negative int or decimal string.

    Floats are rejected for the same reason as money: 0.1 is not 1/10.
    """
    if isinstance(value, bool):
        raise _fail("%s must be a number or decimal string, got boolean" % where)
    if isinstance(value, int):
        weight = Decimal(value)
    elif isinstance(value, str):
        weight = parse_decimal(value, where)
    else:
        raise _fail(
            "%s must be an integer or decimal string, got %s" % (where, _typename(value))
        )
    if weight < 0:
        raise _fail("%s must not be negative, got %s" % (where, weight))
    return weight


def _typename(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


# --------------------------------------------------------------------------
# Allocation: largest remainder method on exact integers
# --------------------------------------------------------------------------


def allocate(total_cents: int, weights, order) -> list:
    """Split `total_cents` across `weights` proportionally, exactly.

    `weights` is a list of non-negative Decimals aligned with `order`, a list
    of integer tie-break keys (lower wins).  Returns a list of integer cents
    that sums to exactly `total_cents`.

    Method: floor each exact share, then hand the leftover cents to the
    largest fractional remainders.  Everything is done in integers after
    clearing the decimal exponents, so there is no rounding anywhere.
    """
    n = len(weights)
    if n == 0:
        raise _fail("cannot split an expense across zero participants")

    # Clear decimal points: scale every weight by 10**max_places so the
    # weights become exact integers and the ratios are unchanged.
    max_places = 0
    for weight in weights:
        exponent = weight.as_tuple().exponent
        if isinstance(exponent, int) and exponent < 0 and -exponent > max_places:
            max_places = -exponent
    int_weights = [scaled_int(weight, max_places) for weight in weights]
    if any(w is None for w in int_weights):  # unreachable: max_places covers all
        raise _fail("split weights are not exactly representable")

    total_weight = sum(int_weights)
    if total_weight <= 0:
        raise _fail("split weights must sum to a positive value")

    # floor(total * w_i / W) with the exact remainder kept alongside.
    allocations = [0] * n
    remainders = []
    allocated = 0
    for i in range(n):
        numerator = total_cents * int_weights[i]
        base, remainder = divmod(numerator, total_weight)
        allocations[i] = base
        allocated += base
        remainders.append((remainder, i))

    leftover = total_cents - allocated
    if leftover:
        # Negative totals cannot occur (amounts are validated non-negative),
        # so leftover is in [0, n).  Hand out one cent each to the largest
        # remainders; ties go to the lower tie-break key for determinism.
        remainders.sort(key=lambda pair: (-pair[0], order[pair[1]]))
        for k in range(leftover):
            allocations[remainders[k][1]] += 1

    return allocations


# --------------------------------------------------------------------------
# Input validation and balance computation
# --------------------------------------------------------------------------

_SPLIT_TYPES = ("equal", "shares", "percent", "exact")


def _require_dict(value, where: str) -> dict:
    if not isinstance(value, dict):
        raise _fail("%s must be an object, got %s" % (where, _typename(value)))
    return value


def _member_map(mapping, index_of, where: str):
    """Validate a {name: value} split map and return aligned (names, values)."""
    _require_dict(mapping, where)
    if not mapping:
        raise _fail("%s must not be empty" % where)
    names = list(mapping.keys())
    for name in names:
        if name not in index_of:
            raise _fail("%s references unknown participant %r" % (where, name))
    # Iterate in the canonical participant order so the tie-break is stable
    # regardless of the order the keys appeared in the input file.
    names.sort(key=lambda name: index_of[name])
    return names


def compute(data) -> dict:
    _require_dict(data, "top-level value")

    if "participants" not in data:
        raise _fail('missing required key "participants"')
    if "expenses" not in data:
        raise _fail('missing required key "expenses"')

    raw_participants = data["participants"]
    if not isinstance(raw_participants, list):
        raise _fail(
            '"participants" must be an array, got %s' % _typename(raw_participants)
        )

    participants = []
    index_of = {}
    for i, name in enumerate(raw_participants):
        if isinstance(name, bool) or not isinstance(name, str):
            raise _fail(
                "participants[%d] must be a string, got %s" % (i, _typename(name))
            )
        if name == "":
            raise _fail("participants[%d] must not be the empty string" % i)
        if name in index_of:
            raise _fail("participants[%d] is a duplicate name: %r" % (i, name))
        index_of[name] = i
        participants.append(name)

    expenses = data["expenses"]
    if not isinstance(expenses, list):
        raise _fail('"expenses" must be an array, got %s' % _typename(expenses))

    balances = [0] * len(participants)

    for e, expense in enumerate(expenses):
        where = "expenses[%d]" % e
        _require_dict(expense, where)

        for key in ("payer", "amount", "split_type"):
            if key not in expense:
                raise _fail('%s is missing required key "%s"' % (where, key))

        payer = expense["payer"]
        if isinstance(payer, bool) or not isinstance(payer, str):
            raise _fail(
                "%s.payer must be a string, got %s" % (where, _typename(payer))
            )
        if payer not in index_of:
            raise _fail("%s.payer is not a known participant: %r" % (where, payer))

        amount = parse_decimal(expense["amount"], "%s.amount" % where)
        if amount < 0:
            raise _fail(
                "%s.amount must not be negative: %s"
                % (where, expense["amount"])
            )
        total_cents = to_cents(amount, "%s.amount" % where)

        split_type = expense["split_type"]
        if isinstance(split_type, bool) or not isinstance(split_type, str):
            raise _fail(
                "%s.split_type must be a string, got %s"
                % (where, _typename(split_type))
            )
        if split_type not in _SPLIT_TYPES:
            raise _fail(
                "%s.split_type must be one of %s, got %r"
                % (where, ", ".join(_SPLIT_TYPES), split_type)
            )

        if split_type == "equal":
            names, shares = _split_equal(expense, where, index_of, total_cents)
        elif split_type == "shares":
            names, shares = _split_shares(expense, where, index_of, total_cents)
        elif split_type == "percent":
            names, shares = _split_percent(expense, where, index_of, total_cents)
        else:
            names, shares = _split_exact(expense, where, index_of, total_cents)

        # Invariant: allocation is exact.  Cheap to check, catastrophic to miss.
        if sum(shares) != total_cents:
            raise _fail(
                "internal error: %s allocation summed to %d, expected %d"
                % (where, sum(shares), total_cents)
            )

        balances[index_of[payer]] += total_cents
        for name, share in zip(names, shares):
            balances[index_of[name]] -= share

    if sum(balances) != 0:
        raise _fail("internal error: balances do not sum to zero")

    transfers = settle(participants, balances)

    return {
        "balances": {participants[i]: balances[i] for i in range(len(participants))},
        "transfers": transfers,
    }


def _split_equal(expense, where, index_of, total_cents):
    if "participants" not in expense:
        raise _fail('%s is missing required key "participants" for an equal split' % where)
    members = expense["participants"]
    field = "%s.participants" % where
    if not isinstance(members, list):
        raise _fail("%s must be an array, got %s" % (field, _typename(members)))
    if not members:
        raise _fail("%s must not be empty" % field)

    seen = set()
    names = []
    for i, name in enumerate(members):
        if isinstance(name, bool) or not isinstance(name, str):
            raise _fail("%s[%d] must be a string, got %s" % (field, i, _typename(name)))
        if name not in index_of:
            raise _fail("%s[%d] is not a known participant: %r" % (field, i, name))
        if name in seen:
            raise _fail("%s[%d] lists %r more than once" % (field, i, name))
        seen.add(name)
        names.append(name)

    names.sort(key=lambda name: index_of[name])
    order = [index_of[name] for name in names]
    weights = [Decimal(1)] * len(names)
    return names, allocate(total_cents, weights, order)


def _split_shares(expense, where, index_of, total_cents):
    if "shares" not in expense:
        raise _fail('%s is missing required key "shares" for a shares split' % where)
    field = "%s.shares" % where
    names = _member_map(expense["shares"], index_of, field)
    weights = [
        parse_weight(expense["shares"][name], "%s[%r]" % (field, name))
        for name in names
    ]
    if not any(weight > 0 for weight in weights):
        raise _fail("%s must contain at least one positive share" % field)
    order = [index_of[name] for name in names]
    return names, allocate(total_cents, weights, order)


def _split_percent(expense, where, index_of, total_cents):
    if "percents" not in expense:
        raise _fail('%s is missing required key "percents" for a percent split' % where)
    field = "%s.percents" % where
    names = _member_map(expense["percents"], index_of, field)
    percents = []
    for name in names:
        value = expense["percents"][name]
        pct = parse_decimal(value, "%s[%r]" % (field, name))
        if pct < 0:
            raise _fail("%s[%r] must not be negative: %s" % (field, name, value))
        percents.append(pct)

    # Sum exactly in integers.  Decimal addition is context-rounded at 28
    # significant digits, which would let "33.333...3" x 3 read as 100.
    places = 0
    for pct in percents:
        exponent = pct.as_tuple().exponent
        if isinstance(exponent, int) and exponent < 0 and -exponent > places:
            places = -exponent
    total_scaled = sum(scaled_int(pct, places) for pct in percents)
    if total_scaled != 100 * (10 ** places):
        raise _fail(
            "%s must sum to exactly 100, got %s"
            % (field, _unscale(total_scaled, places))
        )
    order = [index_of[name] for name in names]
    return names, allocate(total_cents, percents, order)


def _split_exact(expense, where, index_of, total_cents):
    if "amounts" not in expense:
        raise _fail('%s is missing required key "amounts" for an exact split' % where)
    field = "%s.amounts" % where
    names = _member_map(expense["amounts"], index_of, field)
    shares = []
    for name in names:
        value = expense["amounts"][name]
        item = parse_decimal(value, "%s[%r]" % (field, name))
        if item < 0:
            raise _fail("%s[%r] must not be negative: %s" % (field, name, value))
        shares.append(to_cents(item, "%s[%r]" % (field, name)))

    if sum(shares) != total_cents:
        raise _fail(
            "%s sums to %s but the expense amount is %s"
            % (field, _cents_str(sum(shares)), _cents_str(total_cents))
        )
    return names, shares


def _unscale(scaled: int, places: int) -> str:
    """Render an integer-scaled decimal back to a plain string for messages."""
    if places == 0:
        return str(scaled)
    sign = "-" if scaled < 0 else ""
    scaled = abs(scaled)
    divisor = 10 ** places
    return "%s%d.%0*d" % (sign, scaled // divisor, places, scaled % divisor)


def _cents_str(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return "%s%d.%02d" % (sign, cents // 100, cents % 100)


# --------------------------------------------------------------------------
# Settlement
# --------------------------------------------------------------------------


def settle(participants, balances):
    """Greedy largest-creditor / largest-debtor matching.

    Each transfer fully zeroes at least one of the two parties involved, so
    with k non-zero balances we emit at most k - 1 transfers, and k <= n.
    Every emitted transfer is strictly positive.

    This is not guaranteed to be the theoretical minimum number of transfers
    (that problem is NP-hard), but it always meets the n-1 bound and runs in
    O(n log n).
    """
    creditors = sorted(
        ((balances[i], participants[i]) for i in range(len(participants)) if balances[i] > 0),
        key=lambda pair: (-pair[0], pair[1]),
    )
    debtors = sorted(
        ((-balances[i], participants[i]) for i in range(len(participants)) if balances[i] < 0),
        key=lambda pair: (-pair[0], pair[1]),
    )

    transfers = []
    i = j = 0
    credit = creditors[0][0] if creditors else 0
    debt = debtors[0][0] if debtors else 0

    while i < len(creditors) and j < len(debtors):
        amount = credit if credit < debt else debt
        transfers.append(
            {
                "from": debtors[j][1],
                "to": creditors[i][1],
                "amount_cents": amount,
            }
        )
        credit -= amount
        debt -= amount
        if credit == 0:
            i += 1
            if i < len(creditors):
                credit = creditors[i][0]
        if debt == 0:
            j += 1
            if j < len(debtors):
                debt = debtors[j][0]

    return transfers


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

USAGE = "usage: python3 splitfair.py input.json output.json"


def main(argv) -> int:
    if len(argv) != 3:
        sys.stderr.write("splitfair: error: expected 2 arguments, got %d\n%s\n"
                         % (len(argv) - 1, USAGE))
        return 1

    input_path, output_path = argv[1], argv[2]

    try:
        data = load_json(input_path)
        result = compute(data)
    except InvalidInput as exc:
        sys.stderr.write("splitfair: error: %s\n" % exc)
        return 1
    except RecursionError:
        sys.stderr.write("splitfair: error: input JSON is nested too deeply\n")
        return 1

    # Serialise first, write second: if rendering somehow fails we have not
    # left a truncated output file behind.
    text = json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
    try:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(text)
    except OSError as exc:
        sys.stderr.write(
            "splitfair: error: cannot write output file %r: %s\n"
            % (output_path, exc.strerror or exc)
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.setrecursionlimit(20000)
    sys.exit(main(sys.argv))
