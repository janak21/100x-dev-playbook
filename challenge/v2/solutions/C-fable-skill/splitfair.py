#!/usr/bin/env python3
"""splitfair — settle shared expenses to the cent.

Usage: python3 splitfair.py input.json output.json

Reads an expense list, writes per-person net balances (integer cents) and a
settlement plan of at most (participants - 1) transfers. On any invalid input it
writes nothing, prints one diagnostic line to stderr, and exits 1.

All money arithmetic is integer arithmetic. Decimal strings are parsed into
(unscaled integer, decimal places) pairs by hand rather than through float, so
"0.10" means exactly ten cents on every platform.
"""

import json
import os
import re
import sys
import tempfile

# A money/weight literal: optional sign, digits, optional fractional digits.
# Deliberately excludes "1e5", "+1", ".5", "1.", " 1 ", "0x10", "1_000".
_DECIMAL_RE = re.compile(r"\A(-?)([0-9]+)(?:\.([0-9]+))?\Z")

# Guards against pathological literals ("9" * 10_000_000) turning into big-int work.
_MAX_LITERAL_LEN = 64


class InvalidInput(Exception):
    """Raised for every rejected input. The message is user-facing (no internals)."""


# --------------------------------------------------------------------------
# Parsing primitives
# --------------------------------------------------------------------------

def parse_decimal(raw, where):
    """Return (unscaled_int, decimals) for a decimal literal.

    "12.34" -> (1234, 2); 7 -> (7, 0). Exact: no float ever touches the value.
    """
    if isinstance(raw, bool):
        raise InvalidInput("%s: expected a decimal string, got a boolean" % where)
    if isinstance(raw, int):
        return raw, 0
    if isinstance(raw, float):
        raise InvalidInput(
            "%s: got the JSON number %r; use a decimal string such as \"12.34\" "
            "(JSON floats cannot represent cents exactly)" % (where, raw))
    if not isinstance(raw, str):
        raise InvalidInput("%s: expected a decimal string, got %s"
                           % (where, type(raw).__name__))
    if len(raw) > _MAX_LITERAL_LEN:
        raise InvalidInput("%s: numeric literal is too long (max %d characters)"
                           % (where, _MAX_LITERAL_LEN))
    m = _DECIMAL_RE.match(raw)
    if not m:
        raise InvalidInput("%s: %r is not a plain decimal number "
                           "(expected e.g. \"12.34\")" % (where, raw))
    sign, whole, frac = m.group(1), m.group(2), m.group(3) or ""
    value = int(whole + frac)
    if sign:
        value = -value
    return value, len(frac)


def parse_cents(raw, where):
    """Parse a money literal into a non-negative integer number of cents."""
    value, decimals = parse_decimal(raw, where)
    if decimals > 2:
        raise InvalidInput("%s: %r has more than 2 decimal places; amounts are "
                           "exact to the cent" % (where, raw))
    if value < 0:
        raise InvalidInput("%s: %r is negative; amounts must be >= 0" % (where, raw))
    return value * 10 ** (2 - decimals)


def parse_weight(raw, where):
    """Parse a share/percent weight into (unscaled_int, decimals). Floats allowed here.

    Weights are ratios, not money, so a JSON float like 2.5 is unambiguous enough
    to accept; it is routed through repr() and re-parsed as a decimal literal so
    the value stays exact and deterministic. Scientific notation is refused
    because its repr varies with magnitude.
    """
    if isinstance(raw, float):
        if raw != raw or raw in (float("inf"), float("-inf")):
            raise InvalidInput("%s: %r is not a finite number" % (where, raw))
        raw = repr(raw)
        if "e" in raw or "E" in raw:
            raise InvalidInput("%s: scientific notation is not supported; "
                               "use a decimal string" % where)
    value, decimals = parse_decimal(raw, where)
    if value < 0:
        raise InvalidInput("%s: %r is negative; weights must be >= 0" % (where, raw))
    return value, decimals


def scale_weights(pairs):
    """Turn [(value, decimals), ...] into integers over a common power of ten.

    Returns (weights, scale) where scale is 10**max_decimals, so a percent list
    can be checked against 100 * scale. No precision cap is needed: Python
    integers are arbitrary-precision, and _MAX_LITERAL_LEN already bounds how
    many decimal places a single literal can carry.
    """
    k = max(d for _, d in pairs)
    return [v * 10 ** (k - d) for v, d in pairs], 10 ** k


# --------------------------------------------------------------------------
# Allocation
# --------------------------------------------------------------------------

def allocate(total_cents, weights):
    """Split total_cents proportionally to integer weights, exactly.

    Largest-remainder ("Hamilton") method: everyone gets the floor of their exact
    share, then the leftover cents go one each to the largest remainders, ties
    broken by position (callers pass name-sorted groups, so ties break by name).

    Guarantees: sum(result) == total_cents, and every share is either floor or
    ceil of its exact proportional value, i.e. within one cent of exact.
    """
    total_weight = sum(weights)
    if total_weight <= 0:
        raise ValueError("total weight must be positive")  # caller validates first
    shares = []
    remainders = []
    for i, w in enumerate(weights):
        numerator = total_cents * w
        base = numerator // total_weight
        shares.append(base)
        # Remainders share the denominator total_weight, so comparing the
        # numerators is the same as comparing the fractions.
        remainders.append((numerator - base * total_weight, i))
    leftover = total_cents - sum(shares)
    if leftover:
        remainders.sort(key=lambda t: (-t[0], t[1]))
        for _, i in remainders[:leftover]:
            shares[i] += 1
    return shares


# --------------------------------------------------------------------------
# Input validation
# --------------------------------------------------------------------------

def _reject_constant(name):
    raise InvalidInput("JSON contains the non-finite literal %s" % name)


def _no_duplicate_keys(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise InvalidInput("duplicate key %r in a JSON object; refusing to "
                               "guess which value was meant" % key)
        seen[key] = value
    return seen


def load_input(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        raise InvalidInput("cannot read input file %s: %s" % (path, exc.strerror))
    except UnicodeDecodeError:
        raise InvalidInput("input file %s is not valid UTF-8 text" % path)
    # Editors on Windows prepend a byte-order mark; it carries no meaning here.
    if text.startswith("\ufeff"):
        text = text[1:]
    try:
        return json.loads(text, object_pairs_hook=_no_duplicate_keys,
                          parse_constant=_reject_constant)
    except json.JSONDecodeError as exc:
        raise InvalidInput("input file %s is not valid JSON: %s at line %d column %d"
                           % (path, exc.msg, exc.lineno, exc.colno))
    except RecursionError:
        raise InvalidInput("input file %s is nested too deeply" % path)


def read_roster(doc):
    if not isinstance(doc, dict):
        raise InvalidInput("top level of the input must be a JSON object")
    if "participants" not in doc:
        raise InvalidInput("input is missing \"participants\"")
    names = doc["participants"]
    if not isinstance(names, list):
        raise InvalidInput("\"participants\" must be a list of names")
    roster = []
    seen = set()
    for i, name in enumerate(names):
        if not isinstance(name, str):
            raise InvalidInput("participants[%d]: names must be strings" % i)
        if name == "":
            raise InvalidInput("participants[%d]: name must not be empty" % i)
        if name in seen:
            raise InvalidInput("participants[%d]: %r appears twice" % (i, name))
        seen.add(name)
        roster.append(name)
    return roster, seen


def read_group(mapping, roster, where):
    """Validate a name->value object and return its items sorted by name.

    Sorting by name is what makes rounding tie-breaks independent of the order
    the keys happened to appear in the file (requirement 4, determinism).
    """
    if not isinstance(mapping, dict):
        raise InvalidInput("%s: expected an object mapping names to values" % where)
    if not mapping:
        raise InvalidInput("%s: must name at least one participant" % where)
    for name in mapping:
        if name not in roster:
            raise InvalidInput("%s: %r is not in \"participants\"" % (where, name))
    return sorted(mapping.items())


def split_expense(expense, index, roster):
    """Validate one expense; return (payer, [(name, cents), ...])."""
    where = "expenses[%d]" % index
    if not isinstance(expense, dict):
        raise InvalidInput("%s: each expense must be a JSON object" % where)
    for key in ("payer", "amount", "split_type"):
        if key not in expense:
            raise InvalidInput("%s: missing \"%s\"" % (where, key))

    payer = expense["payer"]
    if not isinstance(payer, str):
        raise InvalidInput("%s: \"payer\" must be a string" % where)
    if payer not in roster:
        raise InvalidInput("%s: payer %r is not in \"participants\"" % (where, payer))

    total = parse_cents(expense["amount"], "%s.amount" % where)

    split_type = expense["split_type"]
    if not isinstance(split_type, str):
        raise InvalidInput("%s: \"split_type\" must be a string" % where)

    if split_type == "equal":
        if "participants" not in expense:
            raise InvalidInput("%s: equal split needs \"participants\"" % where)
        group = expense["participants"]
        if not isinstance(group, list):
            raise InvalidInput("%s.participants: must be a list of names" % where)
        if not group:
            raise InvalidInput("%s.participants: must name at least one participant"
                               % where)
        seen = set()
        for j, name in enumerate(group):
            if not isinstance(name, str):
                raise InvalidInput("%s.participants[%d]: names must be strings"
                                   % (where, j))
            if name not in roster:
                raise InvalidInput("%s.participants[%d]: %r is not in \"participants\""
                                   % (where, j, name))
            if name in seen:
                raise InvalidInput("%s.participants[%d]: %r appears twice"
                                   % (where, j, name))
            seen.add(name)
        names = sorted(seen)
        return payer, list(zip(names, allocate(total, [1] * len(names))))

    if split_type == "shares":
        if "shares" not in expense:
            raise InvalidInput("%s: shares split needs \"shares\"" % where)
        items = read_group(expense["shares"], roster, "%s.shares" % where)
        pairs = [parse_weight(v, "%s.shares[%r]" % (where, n)) for n, v in items]
        weights, _ = scale_weights(pairs)
        if sum(weights) <= 0:
            raise InvalidInput("%s.shares: shares must not all be zero" % where)
        names = [n for n, _ in items]
        return payer, list(zip(names, allocate(total, weights)))

    if split_type == "percent":
        if "percents" not in expense:
            raise InvalidInput("%s: percent split needs \"percents\"" % where)
        items = read_group(expense["percents"], roster, "%s.percents" % where)
        pairs = [parse_weight(v, "%s.percents[%r]" % (where, n)) for n, v in items]
        weights, scale = scale_weights(pairs)
        if sum(weights) != 100 * scale:
            raise InvalidInput("%s.percents: percentages must sum to exactly 100"
                               % where)
        names = [n for n, _ in items]
        return payer, list(zip(names, allocate(total, weights)))

    if split_type == "exact":
        if "amounts" not in expense:
            raise InvalidInput("%s: exact split needs \"amounts\"" % where)
        items = read_group(expense["amounts"], roster, "%s.amounts" % where)
        cents = [parse_cents(v, "%s.amounts[%r]" % (where, n)) for n, v in items]
        if sum(cents) != total:
            raise InvalidInput(
                "%s.amounts: shares sum to %d cents but the expense is %d cents"
                % (where, sum(cents), total))
        names = [n for n, _ in items]
        return payer, list(zip(names, cents))

    raise InvalidInput("%s: unknown split_type %r (expected equal, shares, "
                       "percent or exact)" % (where, split_type))


# --------------------------------------------------------------------------
# Settlement
# --------------------------------------------------------------------------

def settle(balances):
    """Greedy settlement: at most (n-1) transfers, every one strictly positive.

    Creditors and debtors are each sorted by amount descending then name, and
    matched head-to-head. Each transfer is min(debt, credit), so it zeroes at
    least one of the two parties; with k non-zero parties that is at most k-1
    transfers, and k <= n.
    """
    creditors = sorted(((v, n) for n, v in balances.items() if v > 0),
                       key=lambda t: (-t[0], t[1]))
    debtors = sorted(((-v, n) for n, v in balances.items() if v < 0),
                     key=lambda t: (-t[0], t[1]))
    transfers = []
    i = j = 0
    credit = debt = 0
    cred_name = debt_name = None
    while True:
        if credit == 0:
            if i >= len(creditors):
                break
            credit, cred_name = creditors[i]
            i += 1
        if debt == 0:
            if j >= len(debtors):
                break
            debt, debt_name = debtors[j]
            j += 1
        amount = credit if credit < debt else debt
        transfers.append({"from": debt_name, "to": cred_name, "amount_cents": amount})
        credit -= amount
        debt -= amount
    return transfers


def compute(doc):
    roster, roster_set = read_roster(doc)
    if "expenses" not in doc:
        raise InvalidInput("input is missing \"expenses\"")
    expenses = doc["expenses"]
    if not isinstance(expenses, list):
        raise InvalidInput("\"expenses\" must be a list")

    balances = dict.fromkeys(roster, 0)
    for index, expense in enumerate(expenses):
        payer, shares = split_expense(expense, index, roster_set)
        total = 0
        for name, cents in shares:
            balances[name] -= cents
            total += cents
        balances[payer] += total

    # Structural check: the accounting above cannot create money, but if a future
    # edit breaks that, fail loudly instead of writing a wrong answer.
    if sum(balances.values()) != 0:
        raise InvalidInput("internal consistency check failed: balances do not "
                           "sum to zero")

    return {"balances": {name: balances[name] for name in sorted(balances)},
            "transfers": settle(balances)}


def write_output(path, result):
    """Serialise first, then write atomically, so a failure leaves no output file."""
    text = json.dumps(result, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":")) + "\n"
    directory = os.path.dirname(os.path.abspath(path))
    try:
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".splitfair-")
    except OSError as exc:
        raise InvalidInput("cannot write output into %s: %s" % (directory, exc.strerror))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise InvalidInput("cannot write output file %s: %s" % (path, exc.strerror))


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: python3 splitfair.py input.json output.json\n")
        return 1
    try:
        result = compute(load_input(argv[1]))
        write_output(argv[2], result)
    except InvalidInput as exc:
        sys.stderr.write("splitfair: %s\n" % exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
