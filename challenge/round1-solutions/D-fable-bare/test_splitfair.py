#!/usr/bin/env python3
"""Automated tests for splitfair.

Run with:  python3 test_splitfair.py
Covers the CLI end-to-end (subprocess) and the internal functions.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PROG = os.path.join(HERE, "splitfair.py")

sys.path.insert(0, HERE)
import splitfair  # noqa: E402
from splitfair import InputError, parse_amount_cents, settle, weighted_shares  # noqa: E402


def run_cli(input_data, raw_text=None, args=None):
    """Run the CLI in a temp dir. Returns (exit_code, stderr, output or None)."""
    with tempfile.TemporaryDirectory() as tmp:
        inp = os.path.join(tmp, "input.json")
        out = os.path.join(tmp, "output.json")
        if raw_text is not None:
            with open(inp, "w") as f:
                f.write(raw_text)
        elif input_data is not None:
            with open(inp, "w") as f:
                json.dump(input_data, f)
        argv = args if args is not None else [inp, out]
        proc = subprocess.run(
            [sys.executable, PROG] + argv, capture_output=True, text=True
        )
        output = None
        if os.path.exists(out):
            with open(out) as f:
                output = json.load(f)
        return proc.returncode, proc.stderr, output


def base(expenses):
    return {"participants": ["Alice", "Bob", "Chad"], "expenses": expenses}


class TestExampleEndToEnd(unittest.TestCase):
    def test_readme_example(self):
        data = {
            "participants": ["Alice", "Bob", "Chad"],
            "expenses": [
                {"payer": "Alice", "amount": "100.00", "split_type": "equal",
                 "participants": ["Alice", "Bob", "Chad"]},
                {"payer": "Bob", "amount": "99.99", "split_type": "shares",
                 "shares": {"Alice": 1, "Bob": 2, "Chad": 3}},
                {"payer": "Chad", "amount": "10.00", "split_type": "percent",
                 "percents": {"Alice": "33.33", "Bob": "33.33", "Chad": "33.34"}},
                {"payer": "Alice", "amount": "50.00", "split_type": "exact",
                 "amounts": {"Bob": "20.00", "Chad": "30.00"}},
            ],
        }
        code, err, output = run_cli(data)
        self.assertEqual(code, 0, err)
        # Hand-computed:
        # equal 10000/3: floors 3333, +1 to Alice -> A 3334, B 3333, C 3333
        # shares 9999 (1:2:3): floors 1666/3333/4999, +1 to Alice
        # percent 1000: floors 333/333/333, +1 to Alice
        # exact: B 2000, C 3000
        # paid: A 15000, B 9999, C 1000
        # owed: A 5335, B 8999, C 11665
        self.assertEqual(output["balances"],
                         {"Alice": 9665, "Bob": 1000, "Chad": -10665})
        self.assertEqual(output["transfers"], [
            {"from": "Chad", "to": "Alice", "amount_cents": 9665},
            {"from": "Chad", "to": "Bob", "amount_cents": 1000},
        ])
        # Transfers restore all balances to zero and respect the n-1 cap.
        self.assertLessEqual(len(output["transfers"]),
                             len(data["participants"]) - 1)

    def test_no_expenses(self):
        code, err, output = run_cli(base([]))
        self.assertEqual(code, 0, err)
        self.assertEqual(output["balances"], {"Alice": 0, "Bob": 0, "Chad": 0})
        self.assertEqual(output["transfers"], [])


class TestExactArithmetic(unittest.TestCase):
    def test_float_trap_0_30_split_3(self):
        # 0.1 + 0.2 != 0.3 in binary floats; must be exact here.
        code, err, output = run_cli(base([
            {"payer": "Alice", "amount": "0.30", "split_type": "equal",
             "participants": ["Alice", "Bob", "Chad"]},
        ]))
        self.assertEqual(code, 0, err)
        self.assertEqual(output["balances"], {"Alice": 20, "Bob": -10, "Chad": -10})

    def test_large_amount_exact(self):
        code, err, output = run_cli(base([
            {"payer": "Alice", "amount": "123456789.01", "split_type": "exact",
             "amounts": {"Bob": "123456789.01"}},
        ]))
        self.assertEqual(code, 0, err)
        self.assertEqual(output["balances"]["Alice"], 12345678901)
        self.assertEqual(output["balances"]["Bob"], -12345678901)

    def test_json_float_literal_two_decimals_ok(self):
        # amount as a JSON number 10.05 must be handled exactly.
        raw = ('{"participants": ["Alice", "Bob", "Chad"], "expenses": ['
               '{"payer": "Alice", "amount": 10.05, "split_type": "exact",'
               ' "amounts": {"Bob": 10.05}}]}')
        code, err, output = run_cli(None, raw_text=raw)
        self.assertEqual(code, 0, err)
        self.assertEqual(output["balances"]["Bob"], -1005)

    def test_integer_amount_ok(self):
        raw = ('{"participants": ["Alice", "Bob", "Chad"], "expenses": ['
               '{"payer": "Alice", "amount": 100, "split_type": "equal",'
               ' "participants": ["Bob"]}]}')
        code, err, output = run_cli(None, raw_text=raw)
        self.assertEqual(code, 0, err)
        self.assertEqual(output["balances"]["Bob"], -10000)

    def test_parse_amount_cents_values(self):
        self.assertEqual(parse_amount_cents("100.00", "t"), 10000)
        self.assertEqual(parse_amount_cents("0.5", "t"), 50)
        self.assertEqual(parse_amount_cents("7", "t"), 700)
        self.assertEqual(parse_amount_cents(7, "t"), 700)


class TestRoundingRules(unittest.TestCase):
    def test_remainder_goes_alphabetically(self):
        # 1.00 among 3: floors 33; 1 extra cent to alphabetically first.
        shares = weighted_shares(100, {"Zed": 1, "Amy": 1, "Bob": 1}, "t")
        self.assertEqual(shares, {"Amy": 34, "Bob": 33, "Zed": 33})

    def test_two_remainder_cents(self):
        # 2.00 among 3: floors 66 each, 2 extras -> Amy and Bob.
        shares = weighted_shares(200, {"Zed": 1, "Amy": 1, "Bob": 1}, "t")
        self.assertEqual(shares, {"Amy": 67, "Bob": 67, "Zed": 66})

    def test_shares_weights_floor(self):
        # 99.99 with 1:2:3 -> floors 1666/3333/4999, remainder 1 -> Alice.
        shares = weighted_shares(9999, {"Alice": 1, "Bob": 2, "Chad": 3}, "t")
        self.assertEqual(shares, {"Alice": 1667, "Bob": 3333, "Chad": 4999})

    def test_percent_split_alphabetical_remainder(self):
        code, err, output = run_cli(base([
            {"payer": "Chad", "amount": "10.00", "split_type": "percent",
             "percents": {"Alice": "33.33", "Bob": "33.33", "Chad": "33.34"}},
        ]))
        self.assertEqual(code, 0, err)
        self.assertEqual(output["balances"],
                         {"Alice": -334, "Bob": -333, "Chad": 667})

    def test_percent_many_decimals_summing_to_100(self):
        # Percents are weights, not money: >2 decimals allowed if sum is 100.
        code, err, output = run_cli(base([
            {"payer": "Alice", "amount": "1.00", "split_type": "percent",
             "percents": {"Alice": "33.335", "Bob": "33.335", "Chad": "33.33"}},
        ]))
        self.assertEqual(code, 0, err)
        self.assertEqual(sum(output["balances"].values()), 0)


class TestSettlement(unittest.TestCase):
    def test_largest_debtor_largest_creditor(self):
        transfers = settle({"A": 500, "B": 300, "C": -700, "D": -100})
        self.assertEqual(transfers, [
            {"from": "C", "to": "A", "amount_cents": 500},
            {"from": "C", "to": "B", "amount_cents": 200},
            {"from": "D", "to": "B", "amount_cents": 100},
        ])
        self.assertLessEqual(len(transfers), 3)

    def test_alphabetical_tie_break(self):
        transfers = settle({"Zed": -50, "Amy": -50, "Bob": 100})
        self.assertEqual(transfers, [
            {"from": "Amy", "to": "Bob", "amount_cents": 50},
            {"from": "Zed", "to": "Bob", "amount_cents": 50},
        ])

    def test_all_zero(self):
        self.assertEqual(settle({"A": 0, "B": 0}), [])

    def test_transfer_cap_and_zeroing(self):
        balances = {"A": 1, "B": 2, "C": 3, "D": -6}
        transfers = settle(dict(balances))
        self.assertLessEqual(len(transfers), len(balances) - 1)
        for t in transfers:
            balances[t["from"]] += t["amount_cents"]
            balances[t["to"]] -= t["amount_cents"]
        self.assertTrue(all(v == 0 for v in balances.values()))


class TestRejections(unittest.TestCase):
    def assert_rejected(self, data=None, raw_text=None, args=None):
        code, err, output = run_cli(data, raw_text=raw_text, args=args)
        self.assertEqual(code, 1)
        self.assertTrue(err.strip(), "expected a message on stderr")
        self.assertIsNone(output, "output.json must not be written on error")
        return err

    def test_malformed_json(self):
        self.assert_rejected(raw_text="{not json")

    def test_missing_input_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "output.json")
            proc = subprocess.run(
                [sys.executable, PROG, os.path.join(tmp, "nope.json"), out],
                capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1)
            self.assertTrue(proc.stderr.strip())
            self.assertFalse(os.path.exists(out))

    def test_wrong_arg_count(self):
        self.assert_rejected(args=[])
        self.assert_rejected(args=["only-one"])

    def test_empty_participants(self):
        self.assert_rejected({"participants": [], "expenses": []})

    def test_duplicate_participants(self):
        self.assert_rejected({"participants": ["A", "B", "A"], "expenses": []})

    def test_participants_not_strings(self):
        self.assert_rejected({"participants": ["A", 3], "expenses": []})

    def test_missing_keys(self):
        self.assert_rejected({"participants": ["A"]})
        self.assert_rejected({"expenses": []})
        self.assert_rejected(raw_text="[]")
        self.assert_rejected(raw_text="null")

    def test_unknown_payer(self):
        self.assert_rejected(base([
            {"payer": "Mallory", "amount": "1.00", "split_type": "equal",
             "participants": ["Alice"]}]))

    def test_unknown_split_participant(self):
        self.assert_rejected(base([
            {"payer": "Alice", "amount": "1.00", "split_type": "equal",
             "participants": ["Alice", "Mallory"]}]))
        self.assert_rejected(base([
            {"payer": "Alice", "amount": "1.00", "split_type": "shares",
             "shares": {"Mallory": 1}}]))
        self.assert_rejected(base([
            {"payer": "Alice", "amount": "1.00", "split_type": "percent",
             "percents": {"Mallory": "100"}}]))
        self.assert_rejected(base([
            {"payer": "Alice", "amount": "1.00", "split_type": "exact",
             "amounts": {"Mallory": "1.00"}}]))

    def test_bad_amounts(self):
        for amount in ["0", "0.00", "-1.00", "1.234", "", ".", "1.",
                       ".5", "1e2", " 1.00", "1,00", "NaN", "1.0.0"]:
            self.assert_rejected(base([
                {"payer": "Alice", "amount": amount, "split_type": "equal",
                 "participants": ["Alice"]}]))

    def test_json_number_amount_three_decimals(self):
        raw = ('{"participants": ["Alice"], "expenses": ['
               '{"payer": "Alice", "amount": 1.005, "split_type": "equal",'
               ' "participants": ["Alice"]}]}')
        self.assert_rejected(raw_text=raw)

    def test_json_negative_and_null_amounts(self):
        raw = ('{"participants": ["Alice"], "expenses": ['
               '{"payer": "Alice", "amount": -5, "split_type": "equal",'
               ' "participants": ["Alice"]}]}')
        self.assert_rejected(raw_text=raw)
        self.assert_rejected(base([
            {"payer": "Alice", "amount": None, "split_type": "equal",
             "participants": ["Alice"]}]))

    def test_percent_sum_not_100(self):
        self.assert_rejected(base([
            {"payer": "Alice", "amount": "1.00", "split_type": "percent",
             "percents": {"Alice": "33.33", "Bob": "33.33", "Chad": "33.33"}}]))
        self.assert_rejected(base([
            {"payer": "Alice", "amount": "1.00", "split_type": "percent",
             "percents": {"Alice": "100.01"}}]))
        # 33.333333... repeated cannot reach exactly 100 with finite decimals.
        self.assert_rejected(base([
            {"payer": "Alice", "amount": "1.00", "split_type": "percent",
             "percents": {"Alice": "33.3333", "Bob": "33.3333",
                          "Chad": "33.3333"}}]))

    def test_exact_sum_mismatch(self):
        self.assert_rejected(base([
            {"payer": "Alice", "amount": "50.00", "split_type": "exact",
             "amounts": {"Bob": "20.00", "Chad": "30.01"}}]))

    def test_exact_amount_three_decimals(self):
        self.assert_rejected(base([
            {"payer": "Alice", "amount": "1.00", "split_type": "exact",
             "amounts": {"Bob": "0.999", "Chad": "0.001"}}]))

    def test_bad_shares(self):
        for w in [0, -1, "2", 1.5, True, None]:
            self.assert_rejected(base([
                {"payer": "Alice", "amount": "1.00", "split_type": "shares",
                 "shares": {"Alice": w}}]))

    def test_empty_split_specs(self):
        self.assert_rejected(base([
            {"payer": "Alice", "amount": "1.00", "split_type": "equal",
             "participants": []}]))
        self.assert_rejected(base([
            {"payer": "Alice", "amount": "1.00", "split_type": "shares",
             "shares": {}}]))
        self.assert_rejected(base([
            {"payer": "Alice", "amount": "1.00", "split_type": "percent",
             "percents": {}}]))
        self.assert_rejected(base([
            {"payer": "Alice", "amount": "1.00", "split_type": "exact",
             "amounts": {}}]))

    def test_duplicate_in_equal_split(self):
        self.assert_rejected(base([
            {"payer": "Alice", "amount": "1.00", "split_type": "equal",
             "participants": ["Bob", "Bob"]}]))

    def test_unknown_split_type(self):
        self.assert_rejected(base([
            {"payer": "Alice", "amount": "1.00", "split_type": "magic",
             "participants": ["Alice"]}]))
        self.assert_rejected(base([
            {"payer": "Alice", "amount": "1.00",
             "participants": ["Alice"]}]))

    def test_expense_not_object(self):
        self.assert_rejected(base(["nope"]))

    def test_duplicate_json_keys(self):
        raw = ('{"participants": ["Alice", "Bob"], "expenses": ['
               '{"payer": "Alice", "amount": "1.00", "split_type": "shares",'
               ' "shares": {"Bob": 1, "Bob": 2}}]}')
        self.assert_rejected(raw_text=raw)


class TestOutputShape(unittest.TestCase):
    def test_all_participants_in_balances_and_ints(self):
        code, err, output = run_cli(base([
            {"payer": "Alice", "amount": "9.00", "split_type": "equal",
             "participants": ["Bob"]}]))
        self.assertEqual(code, 0, err)
        self.assertEqual(set(output["balances"]), {"Alice", "Bob", "Chad"})
        for v in output["balances"].values():
            self.assertIsInstance(v, int)
        for t in output["transfers"]:
            self.assertEqual(set(t), {"from", "to", "amount_cents"})
            self.assertIsInstance(t["amount_cents"], int)
            self.assertGreater(t["amount_cents"], 0)

    def test_payer_in_own_split(self):
        code, err, output = run_cli(base([
            {"payer": "Alice", "amount": "3.00", "split_type": "exact",
             "amounts": {"Alice": "1.00", "Bob": "2.00"}}]))
        self.assertEqual(code, 0, err)
        self.assertEqual(output["balances"],
                         {"Alice": 200, "Bob": -200, "Chad": 0})


if __name__ == "__main__":
    unittest.main(verbosity=2)
