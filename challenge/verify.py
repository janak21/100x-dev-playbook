#!/usr/bin/env python3
"""SplitFair invariant verifier.

Usage: python3 verify.py input.json output.json

Recomputes the reference answer with exact decimal arithmetic and validates the
contestant's output. Exit 0 = PASS, exit 1 = FAIL (reasons printed).
"""
import json
import sys
from decimal import Decimal, InvalidOperation


def fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)


def to_cents(s):
    try:
        d = Decimal(str(s))
    except InvalidOperation:
        fail(f"unparseable amount {s!r}")
    cents = d * 100
    if cents != cents.to_integral_value():
        fail(f"amount {s!r} has more than 2 decimal places")
    return int(cents)


def reference_balances(data):
    people = data["participants"]
    if len(set(people)) != len(people) or not people:
        fail("input invalid (duplicate/empty participants) — this case should not be used with verify.py")
    bal = {p: 0 for p in people}  # cents, positive = is owed

    for exp in data["expenses"]:
        payer = exp["payer"]
        total = to_cents(exp["amount"])
        if total <= 0 or payer not in bal:
            fail("input invalid (bad amount/payer) — error cases are graded by exit code, not verify.py")
        st = exp["split_type"]

        if st == "exact":
            amounts = {n: to_cents(a) for n, a in exp["amounts"].items()}
            if sum(amounts.values()) != total:
                fail("input invalid (exact mismatch) — error case, grade by exit code")
            shares = amounts
        else:
            if st == "equal":
                weights = {n: Decimal(1) for n in exp["participants"]}
            elif st == "shares":
                weights = {n: Decimal(int(w)) for n, w in exp["shares"].items()}
            elif st == "percent":
                weights = {n: Decimal(str(w)) for n, w in exp["percents"].items()}
                if sum(weights.values()) != Decimal(100):
                    fail("input invalid (percents != 100) — error case, grade by exit code")
            else:
                fail(f"unknown split_type {st!r}")
            total_w = sum(weights.values())
            floors = {n: int(Decimal(total) * w / total_w) for n, w in weights.items()}
            remainder = total - sum(floors.values())
            for n in sorted(weights):
                if remainder <= 0:
                    break
                floors[n] += 1
                remainder -= 1
            shares = floors

        for n, owed in shares.items():
            if n not in bal:
                fail(f"unknown participant {n!r} in split")
            bal[n] -= owed
        bal[payer] += total
    return bal


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    with open(sys.argv[1]) as f:
        data = json.load(f)
    try:
        with open(sys.argv[2]) as f:
            out = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        fail(f"cannot read output.json: {e}")

    ref = reference_balances(data)

    # 1. balances match the reference exactly
    got = out.get("balances")
    if not isinstance(got, dict):
        fail("output missing 'balances' dict")
    for p, expected in ref.items():
        if p not in got:
            fail(f"balances missing participant {p!r}")
        if int(got[p]) != expected:
            fail(f"balance for {p}: expected {expected} cents, got {got[p]}")
    extra = set(got) - set(ref)
    if extra:
        fail(f"balances has unknown names: {extra}")

    # 2. transfers settle every balance to exactly zero
    transfers = out.get("transfers")
    if not isinstance(transfers, list):
        fail("output missing 'transfers' list")
    work = dict(ref)
    for t in transfers:
        frm, to, amt = t.get("from"), t.get("to"), t.get("amount_cents")
        if frm not in work or to not in work:
            fail(f"transfer references unknown name: {t}")
        if frm == to:
            fail(f"self-transfer: {t}")
        if not isinstance(amt, int) or amt <= 0:
            fail(f"transfer amount must be a positive integer in cents: {t}")
        work[frm] += amt
        work[to] -= amt
    residue = {p: v for p, v in work.items() if v != 0}
    if residue:
        fail(f"transfers do not settle balances to zero; residue (cents): {residue}")

    # 3. transfer count bound
    n = len(data["participants"])
    if len(transfers) > n - 1:
        fail(f"{len(transfers)} transfers used; at most {n - 1} allowed")

    print(f"PASS: balances exact, {len(transfers)} transfer(s) settle to zero within bound")
    sys.exit(0)


if __name__ == "__main__":
    main()
