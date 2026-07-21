#!/usr/bin/env python3
"""Tests for splitfair. Run: python3 -m unittest -v (from this directory)."""

import json
import os
import random
import subprocess
import sys
import tempfile
import time
import unittest
from fractions import Fraction

import splitfair

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.join(HERE, "splitfair.py")


def run_cli(input_text, keep_output=False, args=None):
    """Run the program as the user does. Returns (returncode, stderr, output_or_None)."""
    workdir = tempfile.mkdtemp()
    in_path = os.path.join(workdir, "input.json")
    out_path = os.path.join(workdir, "output.json")
    with open(in_path, "w", encoding="utf-8") as fh:
        fh.write(input_text)
    argv = [sys.executable, PROGRAM] + (args if args is not None else [in_path, out_path])
    proc = subprocess.run(argv, capture_output=True, text=True)
    raw = None
    if os.path.exists(out_path):
        with open(out_path, "rb") as fh:
            raw = fh.read()
    return proc.returncode, proc.stderr, raw


def settle_doc(doc):
    """Happy-path helper: run the CLI on a document, assert success, return result."""
    code, err, raw = run_cli(json.dumps(doc))
    assert code == 0, "expected success, got %d: %s" % (code, err)
    return json.loads(raw.decode("utf-8"))


def assert_rejected(case, doc_or_text):
    text = doc_or_text if isinstance(doc_or_text, str) else json.dumps(doc_or_text)
    code, err, raw = run_cli(text)
    case.assertEqual(code, 1, "expected exit 1, stderr=%r" % err)
    case.assertIsNone(raw, "output file must not be created on invalid input")
    case.assertTrue(err.strip(), "an error message on stderr is required")
    case.assertNotIn("Traceback", err, "errors must not leak internals")
    return err


# ---------------------------------------------------------------------------
# Allocation unit tests
# ---------------------------------------------------------------------------

class TestAllocate(unittest.TestCase):
    def test_exact_division(self):
        self.assertEqual(splitfair.allocate(1000, [1, 1]), [500, 500])

    def test_indivisible_cent_goes_to_first_tie(self):
        # 0.01 among three: one cent, deterministic recipient (first by position).
        self.assertEqual(splitfair.allocate(1, [1, 1, 1]), [1, 0, 0])

    def test_ten_dollars_three_ways(self):
        shares = splitfair.allocate(1000, [1, 1, 1])
        self.assertEqual(sum(shares), 1000)
        self.assertEqual(sorted(shares), [333, 333, 334])

    def test_zero_total(self):
        self.assertEqual(splitfair.allocate(0, [3, 1]), [0, 0])

    def test_zero_weight_gets_nothing(self):
        self.assertEqual(splitfair.allocate(100, [0, 1]), [0, 100])

    def test_conservation_and_fairness_random(self):
        rng = random.Random(20260721)
        for _ in range(3000):
            n = rng.randint(1, 12)
            weights = [rng.randint(0, 50) for _ in range(n)]
            if sum(weights) == 0:
                weights[0] = 1
            total = rng.randint(0, 5_000_00)
            shares = splitfair.allocate(total, weights)
            self.assertEqual(sum(shares), total)          # requirement 1
            self.assertTrue(all(s >= 0 for s in shares))
            wsum = sum(weights)
            for s, w in zip(shares, weights):
                exact = Fraction(total * w, wsum)
                self.assertLess(abs(Fraction(s) - exact), 1)  # requirement 2


# ---------------------------------------------------------------------------
# Split semantics
# ---------------------------------------------------------------------------

class TestSplits(unittest.TestCase):
    def test_equal_split_leftover_cent(self):
        out = settle_doc({
            "participants": ["Ana", "Bob", "Cy"],
            "expenses": [{"payer": "Ana", "amount": "10.00", "split_type": "equal",
                          "participants": ["Ana", "Bob", "Cy"]}],
        })
        # Ana paid 1000, owes 334 (first alphabetically takes the odd cent).
        self.assertEqual(out["balances"], {"Ana": 666, "Bob": -333, "Cy": -333})

    def test_shares(self):
        out = settle_doc({
            "participants": ["Ana", "Bob"],
            "expenses": [{"payer": "Ana", "amount": "12.34", "split_type": "shares",
                          "shares": {"Ana": 1, "Bob": 3}}],
        })
        # 12.34 split 1:3 is 308.5 / 925.5; the odd cent goes to Ana (name tie-break),
        # so Ana paid 1234 and owes 309.
        self.assertEqual(out["balances"], {"Ana": 925, "Bob": -925})

    def test_fractional_share_weights_allowed(self):
        out = settle_doc({
            "participants": ["Ana", "Bob"],
            "expenses": [{"payer": "Ana", "amount": "10.00", "split_type": "shares",
                          "shares": {"Ana": 2.5, "Bob": "7.5"}}],
        })
        self.assertEqual(out["balances"], {"Ana": 750, "Bob": -750})

    def test_percent(self):
        out = settle_doc({
            "participants": ["Ana", "Bob"],
            "expenses": [{"payer": "Bob", "amount": "12.34", "split_type": "percent",
                          "percents": {"Ana": "33.33", "Bob": "66.67"}}],
        })
        self.assertEqual(out["balances"], {"Ana": -411, "Bob": 411})

    def test_percent_as_json_floats_is_accepted_and_exact(self):
        # Ratios, not money: repr(33.33) == "33.33", so the value stays exact.
        out = settle_doc({
            "participants": ["Ana", "Bob"],
            "expenses": [{"payer": "Bob", "amount": "12.34", "split_type": "percent",
                          "percents": {"Ana": 33.33, "Bob": 66.67}}],
        })
        self.assertEqual(out["balances"], {"Ana": -411, "Bob": 411})

    def test_exact(self):
        out = settle_doc({
            "participants": ["Ana", "Bob"],
            "expenses": [{"payer": "Ana", "amount": "12.34", "split_type": "exact",
                          "amounts": {"Ana": "4.00", "Bob": "8.34"}}],
        })
        self.assertEqual(out["balances"], {"Ana": 834, "Bob": -834})

    def test_payer_need_not_be_in_the_split(self):
        out = settle_doc({
            "participants": ["Ana", "Bob", "Cy"],
            "expenses": [{"payer": "Cy", "amount": "1.00", "split_type": "equal",
                          "participants": ["Ana", "Bob"]}],
        })
        self.assertEqual(out["balances"], {"Ana": -50, "Bob": -50, "Cy": 100})

    def test_zero_amount(self):
        out = settle_doc({
            "participants": ["Ana", "Bob"],
            "expenses": [{"payer": "Ana", "amount": "0.00", "split_type": "equal",
                          "participants": ["Ana", "Bob"]}],
        })
        self.assertEqual(out, {"balances": {"Ana": 0, "Bob": 0}, "transfers": []})

    def test_empty_expenses(self):
        out = settle_doc({"participants": ["Ana", "Bob"], "expenses": []})
        self.assertEqual(out, {"balances": {"Ana": 0, "Bob": 0}, "transfers": []})

    def test_empty_roster_and_no_expenses(self):
        out = settle_doc({"participants": [], "expenses": []})
        self.assertEqual(out, {"balances": {}, "transfers": []})

    def test_unicode_names_round_trip(self):
        out = settle_doc({
            "participants": ["Ana", "Bö", "文"],
            "expenses": [{"payer": "文", "amount": "3.00", "split_type": "equal",
                          "participants": ["Ana", "Bö", "文"]}],
        })
        self.assertEqual(out["balances"], {"Ana": -100, "Bö": -100, "文": 200})

    def test_integer_amount_accepted(self):
        out = settle_doc({
            "participants": ["Ana", "Bob"],
            "expenses": [{"payer": "Ana", "amount": 5, "split_type": "equal",
                          "participants": ["Ana", "Bob"]}],
        })
        self.assertEqual(out["balances"], {"Ana": 250, "Bob": -250})

    def test_large_amount_no_precision_loss(self):
        out = settle_doc({
            "participants": ["Ana", "Bob"],
            "expenses": [{"payer": "Ana", "amount": "99999999999999.99",
                          "split_type": "equal", "participants": ["Ana", "Bob"]}],
        })
        self.assertEqual(out["balances"]["Ana"] + out["balances"]["Bob"], 0)
        # Ana takes the odd cent of 9999999999999999, so she owes 5000000000000000.
        self.assertEqual(out["balances"]["Ana"], 9999999999999999 - 5000000000000000)

    def test_utf8_bom_is_tolerated(self):
        text = "﻿" + json.dumps({"participants": ["Ana"], "expenses": []})
        code, err, raw = run_cli(text)
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(raw.decode("utf-8"))["balances"], {"Ana": 0})

    def test_high_precision_weights_still_conserve_money(self):
        out = settle_doc({
            "participants": ["Ana", "Bob"],
            "expenses": [{"payer": "Ana", "amount": "1.00", "split_type": "shares",
                          "shares": {"Ana": "0." + "0" * 30 + "1", "Bob": 1}}],
        })
        self.assertEqual(sum(out["balances"].values()), 0)
        self.assertEqual(out["balances"], {"Ana": 100, "Bob": -100})

    def test_key_order_does_not_change_the_answer(self):
        a = settle_doc({
            "participants": ["Ana", "Bob", "Cy"],
            "expenses": [{"payer": "Ana", "amount": "0.01", "split_type": "shares",
                          "shares": {"Cy": 1, "Bob": 1, "Ana": 1}}],
        })
        b = settle_doc({
            "participants": ["Cy", "Bob", "Ana"],
            "expenses": [{"payer": "Ana", "amount": "0.01", "split_type": "shares",
                          "shares": {"Ana": 1, "Bob": 1, "Cy": 1}}],
        })
        self.assertEqual(a, b)


# ---------------------------------------------------------------------------
# Settlement plan
# ---------------------------------------------------------------------------

class TestSettlement(unittest.TestCase):
    def test_transfers_settle_and_are_bounded(self):
        out = settle_doc({
            "participants": ["Ana", "Bob", "Cy", "Di"],
            "expenses": [
                {"payer": "Ana", "amount": "40.00", "split_type": "equal",
                 "participants": ["Ana", "Bob", "Cy", "Di"]},
                {"payer": "Bob", "amount": "20.00", "split_type": "equal",
                 "participants": ["Cy", "Di"]},
            ],
        })
        self.assertLessEqual(len(out["transfers"]), 3)
        self.check_plan(out)

    def test_no_transfers_when_settled(self):
        out = settle_doc({
            "participants": ["Ana", "Bob"],
            "expenses": [
                {"payer": "Ana", "amount": "10.00", "split_type": "equal",
                 "participants": ["Ana", "Bob"]},
                {"payer": "Bob", "amount": "10.00", "split_type": "equal",
                 "participants": ["Ana", "Bob"]},
            ],
        })
        self.assertEqual(out["transfers"], [])

    def check_plan(self, out):
        balances = dict(out["balances"])
        self.assertEqual(sum(balances.values()), 0)
        nonzero = sum(1 for v in balances.values() if v != 0)
        self.assertLessEqual(len(out["transfers"]), max(len(balances) - 1, 0))
        self.assertLessEqual(len(out["transfers"]), max(nonzero - 1, 0))
        for t in out["transfers"]:
            self.assertGreater(t["amount_cents"], 0)          # requirement 3
            self.assertNotEqual(t["from"], t["to"])
            self.assertIn(t["from"], balances)
            self.assertIn(t["to"], balances)
            balances[t["from"]] += t["amount_cents"]
            balances[t["to"]] -= t["amount_cents"]
        self.assertTrue(all(v == 0 for v in balances.values()),
                        "transfers must settle everyone: %r" % balances)

    def test_randomized_end_to_end(self):
        rng = random.Random(7)
        for trial in range(60):
            n = rng.randint(1, 9)
            people = ["p%02d" % i for i in range(n)]
            expenses = []
            for _ in range(rng.randint(0, 25)):
                group = rng.sample(people, rng.randint(1, n))
                amount = "%d.%02d" % (rng.randint(0, 500), rng.randint(0, 99))
                kind = rng.choice(["equal", "shares", "percent", "exact"])
                e = {"payer": rng.choice(people), "amount": amount, "split_type": kind}
                if kind == "equal":
                    e["participants"] = group
                elif kind == "shares":
                    w = {p: rng.randint(0, 9) for p in group}
                    if sum(w.values()) == 0:
                        w[group[0]] = 1
                    e["shares"] = w
                elif kind == "percent":
                    # integer percents summing to exactly 100
                    cuts = sorted(rng.randint(0, 100) for _ in range(len(group) - 1))
                    prev, pct = 0, []
                    for c in cuts + [100]:
                        pct.append(c - prev)
                        prev = c
                    e["percents"] = {p: str(v) for p, v in zip(group, pct)}
                else:
                    cents = int(round(float(amount) * 100))
                    parts = [0] * len(group)
                    for _ in range(cents):
                        parts[rng.randrange(len(group))] += 1
                    e["amounts"] = {p: "%d.%02d" % divmod(v, 100)
                                    for p, v in zip(group, parts)}
                expenses.append(e)
            out = settle_doc({"participants": people, "expenses": expenses})
            self.assertEqual(set(out["balances"]), set(people))
            self.check_plan(out)


# ---------------------------------------------------------------------------
# Invalid input (requirement 6)
# ---------------------------------------------------------------------------

class TestRejection(unittest.TestCase):
    def base(self, **overrides):
        expense = {"payer": "Ana", "amount": "10.00", "split_type": "equal",
                   "participants": ["Ana", "Bob"]}
        expense.update(overrides)
        return {"participants": ["Ana", "Bob"], "expenses": [expense]}

    def test_not_json(self):
        assert_rejected(self, "{not json")

    def test_empty_file(self):
        assert_rejected(self, "")

    def test_top_level_is_a_list(self):
        assert_rejected(self, "[]")

    def test_top_level_is_a_string(self):
        assert_rejected(self, '"hello"')

    def test_missing_participants(self):
        assert_rejected(self, {"expenses": []})

    def test_missing_expenses(self):
        assert_rejected(self, {"participants": ["Ana"]})

    def test_participants_not_a_list(self):
        assert_rejected(self, {"participants": {"Ana": 1}, "expenses": []})

    def test_duplicate_participant(self):
        assert_rejected(self, {"participants": ["Ana", "Ana"], "expenses": []})

    def test_non_string_participant(self):
        assert_rejected(self, {"participants": [1], "expenses": []})

    def test_empty_participant_name(self):
        assert_rejected(self, {"participants": [""], "expenses": []})

    def test_duplicate_json_keys(self):
        assert_rejected(self, '{"participants":["Ana","Bob"],"expenses":[{"payer":"Ana",'
                              '"amount":"1.00","split_type":"shares",'
                              '"shares":{"Ana":1,"Ana":3}}]}')

    def test_nan_literal(self):
        assert_rejected(self, '{"participants":["Ana"],"expenses":[{"payer":"Ana",'
                              '"amount":NaN,"split_type":"equal",'
                              '"participants":["Ana"]}]}')

    def test_infinity_literal(self):
        assert_rejected(self, '{"participants":["Ana"],"expenses":[{"payer":"Ana",'
                              '"amount":Infinity,"split_type":"equal",'
                              '"participants":["Ana"]}]}')

    def test_float_amount(self):
        err = assert_rejected(self, self.base(amount=10.0))
        self.assertIn("decimal string", err)

    def test_amount_with_three_decimals(self):
        assert_rejected(self, self.base(amount="10.005"))

    def test_negative_amount(self):
        assert_rejected(self, self.base(amount="-1.00"))

    def test_amount_scientific_notation(self):
        assert_rejected(self, self.base(amount="1e2"))

    def test_amount_with_whitespace(self):
        assert_rejected(self, self.base(amount=" 10.00 "))

    def test_amount_with_currency_symbol(self):
        assert_rejected(self, self.base(amount="$10.00"))

    def test_amount_with_thousands_separator(self):
        assert_rejected(self, self.base(amount="1,000.00"))

    def test_amount_empty_string(self):
        assert_rejected(self, self.base(amount=""))

    def test_amount_absurdly_long(self):
        assert_rejected(self, self.base(amount="9" * 500 + ".00"))

    def test_amount_is_null(self):
        assert_rejected(self, self.base(amount=None))

    def test_amount_is_boolean(self):
        assert_rejected(self, self.base(amount=True))

    def test_expense_not_an_object(self):
        assert_rejected(self, {"participants": ["Ana"], "expenses": ["nope"]})

    def test_expenses_not_a_list(self):
        assert_rejected(self, {"participants": ["Ana"], "expenses": {}})

    def test_missing_payer(self):
        doc = self.base()
        del doc["expenses"][0]["payer"]
        assert_rejected(self, doc)

    def test_unknown_payer(self):
        assert_rejected(self, self.base(payer="Zed"))

    def test_unknown_split_type(self):
        assert_rejected(self, self.base(split_type="proportional"))

    def test_split_type_wrong_case(self):
        assert_rejected(self, self.base(split_type="Equal"))

    def test_equal_missing_group(self):
        doc = self.base()
        del doc["expenses"][0]["participants"]
        assert_rejected(self, doc)

    def test_equal_empty_group(self):
        assert_rejected(self, self.base(participants=[]))

    def test_equal_group_has_unknown_name(self):
        assert_rejected(self, self.base(participants=["Ana", "Zed"]))

    def test_equal_group_has_duplicate(self):
        assert_rejected(self, self.base(participants=["Ana", "Ana"]))

    def test_shares_all_zero(self):
        assert_rejected(self, self.base(split_type="shares", shares={"Ana": 0, "Bob": 0}))

    def test_shares_negative(self):
        assert_rejected(self, self.base(split_type="shares", shares={"Ana": -1, "Bob": 2}))

    def test_shares_empty_object(self):
        assert_rejected(self, self.base(split_type="shares", shares={}))

    def test_shares_not_an_object(self):
        assert_rejected(self, self.base(split_type="shares", shares=[1, 2]))

    def test_shares_non_numeric(self):
        assert_rejected(self, self.base(split_type="shares", shares={"Ana": "lots"}))

    def test_percent_sum_below_100(self):
        assert_rejected(self, self.base(split_type="percent",
                                        percents={"Ana": "33.33", "Bob": "66.66"}))

    def test_percent_sum_above_100(self):
        assert_rejected(self, self.base(split_type="percent",
                                        percents={"Ana": "50", "Bob": "50.01"}))

    def test_percent_negative(self):
        assert_rejected(self, self.base(split_type="percent",
                                        percents={"Ana": "-10", "Bob": "110"}))

    def test_percent_scientific_notation(self):
        assert_rejected(self, self.base(split_type="percent",
                                        percents={"Ana": 1e-9, "Bob": "100"}))

    def test_exact_sum_mismatch(self):
        assert_rejected(self, self.base(split_type="exact",
                                        amounts={"Ana": "4.00", "Bob": "8.34"}))

    def test_exact_negative_share(self):
        assert_rejected(self, self.base(amount="10.00", split_type="exact",
                                        amounts={"Ana": "-1.00", "Bob": "11.00"}))

    def test_exact_three_decimals(self):
        assert_rejected(self, self.base(amount="10.00", split_type="exact",
                                        amounts={"Ana": "5.005", "Bob": "4.995"}))

    def test_deeply_nested_json(self):
        assert_rejected(self, "[" * 100000 + "]" * 100000)

    def test_wrong_argument_count(self):
        proc = subprocess.run([sys.executable, PROGRAM], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("usage", proc.stderr)

    def test_missing_input_file(self):
        code, err, _ = run_cli("{}", args=["/nonexistent/nope.json", "/tmp/out.json"])
        self.assertEqual(code, 1)
        self.assertTrue(err.strip())

    def test_unwritable_output_path(self):
        code, err, _ = run_cli('{"participants":[],"expenses":[]}',
                               args=[os.devnull, "/nonexistent-dir/out.json"])
        self.assertEqual(code, 1)
        self.assertTrue(err.strip())

    def test_a_later_bad_expense_writes_nothing(self):
        doc = {"participants": ["Ana", "Bob"], "expenses": [
            {"payer": "Ana", "amount": "1.00", "split_type": "equal",
             "participants": ["Ana", "Bob"]},
            {"payer": "Ana", "amount": "oops", "split_type": "equal",
             "participants": ["Ana", "Bob"]},
        ]}
        err = assert_rejected(self, doc)
        self.assertIn("expenses[1]", err)


# ---------------------------------------------------------------------------
# Determinism and performance (requirements 4 and 5)
# ---------------------------------------------------------------------------

class TestOperational(unittest.TestCase):
    def big_doc(self):
        rng = random.Random(99)
        people = ["person-%02d" % i for i in range(50)]
        expenses = []
        for i in range(5000):
            kind = ["equal", "shares", "percent", "exact"][i % 4]
            group = rng.sample(people, rng.randint(2, 50))
            amount = "%d.%02d" % (rng.randint(1, 9999), rng.randint(0, 99))
            e = {"payer": rng.choice(people), "amount": amount, "split_type": kind}
            if kind == "equal":
                e["participants"] = group
            elif kind == "shares":
                e["shares"] = {p: rng.randint(1, 20) for p in group}
            elif kind == "percent":
                cuts = sorted(rng.randint(0, 10000) for _ in range(len(group) - 1))
                prev, pct = 0, []
                for c in cuts + [10000]:
                    pct.append("%d.%02d" % divmod(c - prev, 100))
                    prev = c
                e["percents"] = dict(zip(group, pct))
            else:
                cents = int(amount.replace(".", ""))
                parts = [cents // len(group)] * len(group)
                parts[0] += cents - sum(parts)
                e["amounts"] = {p: "%d.%02d" % divmod(v, 100)
                                for p, v in zip(group, parts)}
            expenses.append(e)
        return {"participants": people, "expenses": expenses}

    def test_byte_identical_across_runs(self):
        doc = {"participants": ["Zoe", "Ana", "Bob", "Cy"], "expenses": [
            {"payer": "Zoe", "amount": "10.01", "split_type": "equal",
             "participants": ["Zoe", "Ana", "Bob"]},
            {"payer": "Ana", "amount": "7.77", "split_type": "shares",
             "shares": {"Cy": 2, "Ana": 1}},
        ]}
        text = json.dumps(doc)
        first = run_cli(text)[2]
        for _ in range(4):
            self.assertEqual(run_cli(text)[2], first)

    def test_scale_50_participants_5000_expenses(self):
        text = json.dumps(self.big_doc())
        start = time.time()
        code, err, raw = run_cli(text)
        elapsed = time.time() - start
        self.assertEqual(code, 0, err)
        self.assertLess(elapsed, 10.0, "took %.2fs" % elapsed)
        out = json.loads(raw.decode("utf-8"))
        self.assertEqual(sum(out["balances"].values()), 0)
        TestSettlement.check_plan(self, out)


if __name__ == "__main__":
    unittest.main()
