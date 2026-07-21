#!/usr/bin/env python3
"""SplitFair v2 invariant verifier — algorithm-agnostic.

Unlike v1, this does NOT compare against one prescribed algorithm. It checks
invariants that any correct solution must satisfy, so contestants are free to
choose their own rounding and settlement strategies.

Usage:
  verify2.py fairness  input.json output.json   # single-expense: exact fairness
  verify2.py conserve  input.json output.json   # multi-expense: conservation + settlement
Exit 0 = PASS.
"""
import json
import sys
from decimal import Decimal
from fractions import Fraction


def fail(m):
    print(f"FAIL: {m}")
    sys.exit(1)


def cents(s):
    return int(Decimal(str(s)) * 100)


def load(inp, out):
    data = json.load(open(inp))
    try:
        o = json.load(open(out))
    except Exception as e:
        fail(f"cannot read output: {e}")
    if not isinstance(o.get("balances"), dict):
        fail("missing 'balances' dict")
    if not isinstance(o.get("transfers"), list):
        fail("missing 'transfers' list")
    return data, o


def check_settlement(data, o):
    """Transfers must zero out every balance, be positive, and be well-formed."""
    bal = {k: int(v) for k, v in o["balances"].items()}
    people = set(data["participants"])
    if set(bal) != people:
        fail(f"balances keys {set(bal) ^ people} do not match participants")
    if sum(bal.values()) != 0:
        fail(f"balances do not sum to zero (sum={sum(bal.values())}) — money created or destroyed")
    work = dict(bal)
    for t in o["transfers"]:
        f, to, a = t.get("from"), t.get("to"), t.get("amount_cents")
        if f not in work or to not in work:
            fail(f"transfer references unknown participant: {t}")
        if f == to:
            fail(f"self-transfer: {t}")
        if not isinstance(a, int) or isinstance(a, bool) or a <= 0:
            fail(f"transfer amount must be a positive integer number of cents: {t}")
        work[f] += a
        work[to] -= a
    residue = {k: v for k, v in work.items() if v != 0}
    if residue:
        fail(f"transfers leave residue (cents): {residue}")
    n = len(people)
    if len(o["transfers"]) > n - 1:
        fail(f"{len(o['transfers'])} transfers exceeds the n-1 = {n-1} bound")
    return bal


def total_paid(data):
    paid = {p: 0 for p in data["participants"]}
    for e in data["expenses"]:
        paid[e["payer"]] += cents(e["amount"])
    return paid


def main():
    mode, inp, out = sys.argv[1], sys.argv[2], sys.argv[3]
    data, o = load(inp, out)
    bal = check_settlement(data, o)
    paid = total_paid(data)

    if mode == "conserve":
        owed_total = sum(paid.values()) - sum(bal.values())
        if owed_total != sum(paid.values()):
            fail("total owed != total paid")
        print(f"PASS: conservation holds, {len(o['transfers'])} transfer(s) settle to zero within bound")
        sys.exit(0)

    if mode == "fairness":
        # Single-expense inputs only: implied share per person = paid - balance.
        if len(data["expenses"]) != 1:
            fail("fairness mode requires a single-expense input")
        e = data["expenses"][0]
        total = cents(e["amount"])
        owed = {p: paid[p] - bal[p] for p in data["participants"]}
        if sum(owed.values()) != total:
            fail(f"shares sum to {sum(owed.values())} cents, expected exactly {total}")
        if any(v < 0 for v in owed.values()):
            fail(f"negative share allocated: {owed}")
        # exact proportional target from declared weights
        st = e["split_type"]
        if st == "equal":
            w = {p: Fraction(1) for p in e["participants"]}
        elif st == "shares":
            w = {p: Fraction(int(v)) for p, v in e["shares"].items()}
        elif st == "percent":
            w = {p: Fraction(Decimal(str(v))) for p, v in e["percents"].items()}
        else:
            fail(f"fairness mode does not handle split_type {st}")
        W = sum(w.values())
        for p in data["participants"]:
            target = Fraction(total) * w.get(p, Fraction(0)) / W
            got = owed[p]
            if abs(Fraction(got) - target) >= 1:
                fail(f"{p}: share {got} deviates from exact proportional {float(target):.4f} by >=1 cent")
        for p in data["participants"]:
            if p not in w and owed[p] != 0:
                fail(f"{p} is not in this split but was allocated {owed[p]} cents")
        print(f"PASS: shares sum exactly, every share within 1 cent of proportional, settlement valid")
        sys.exit(0)

    fail(f"unknown mode {mode}")


if __name__ == "__main__":
    main()
