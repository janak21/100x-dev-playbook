"""Tests for splitfair.

Two layers:
  1. CLI tests (subprocess) — exercise the real contract the grader uses:
     argv, exit codes, stderr, output-file behavior.
  2. Unit tests — direct calls into splitfair for the arithmetic core.

Run:  python3 -m unittest test_splitfair -v
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import splitfair  # noqa: E402

PROGRAM = os.path.join(os.path.dirname(os.path.abspath(__file__)), "splitfair.py")


def run_cli(input_data, tmpdir, raw_text=None):
    """Run the CLI on input_data (a Python object, or raw_text JSON string).
    Returns (exit_code, stderr, output_object_or_None, output_path)."""
    in_path = os.path.join(tmpdir, "input.json")
    out_path = os.path.join(tmpdir, "output.json")
    with open(in_path, "w", encoding="utf-8") as fh:
        fh.write(raw_text if raw_text is not None else json.dumps(input_data))
    proc = subprocess.run(
        [sys.executable, PROGRAM, in_path, out_path],
        capture_output=True, text=True,
    )
    output = None
    if os.path.exists(out_path):
        with open(out_path, "r", encoding="utf-8") as fh:
            output = json.load(fh)
    return proc.returncode, proc.stderr, output, out_path


class CliCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def ok(self, input_data, raw_text=None):
        code, stderr, output, _ = run_cli(input_data, self.tmpdir, raw_text)
        self.assertEqual(code, 0, "expected success, stderr: %s" % stderr)
        self.assertIsNotNone(output, "output.json was not written")
        return output

    def rejected(self, input_data, raw_text=None):
        code, stderr, output, out_path = run_cli(input_data, self.tmpdir, raw_text)
        self.assertEqual(code, 1, "expected rejection but got exit %d" % code)
        self.assertFalse(os.path.exists(out_path),
                         "output file must NOT be written on invalid input")
        self.assertTrue(stderr.strip(), "stderr must carry a useful message")
        return stderr


class TestHappyPaths(CliCase):
    def test_spec_example_end_to_end(self):
        """The exact example from the task, verified by hand:
        E1 equal 10000/3 -> 3334/3333/3333 (Alice gets the remainder cent)
        E2 shares 9999 @1:2:3 -> floors 1666/3333/4999, remainder->Alice: 1667
        E3 percent 1000 @33.33/33.33/33.34 -> floors 333/333/333, rem->Alice: 334
        E4 exact Bob 2000, Chad 3000
        paid: A 15000, B 9999, C 1000; owed: A 5335, B 8999, C 11665."""
        output = self.ok({
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
        })
        self.assertEqual(output["balances"],
                         {"Alice": 9665, "Bob": 1000, "Chad": -10665})
        self.assertEqual(output["transfers"], [
            {"from": "Chad", "to": "Alice", "amount_cents": 9665},
            {"from": "Chad", "to": "Bob", "amount_cents": 1000},
        ])

    def test_empty_expenses_all_zero(self):
        output = self.ok({"participants": ["A", "B"], "expenses": []})
        self.assertEqual(output["balances"], {"A": 0, "B": 0})
        self.assertEqual(output["transfers"], [])

    def test_equal_remainder_alphabetical(self):
        # 100.01 among Zed, Amy, Mia -> 3333 each + 2 remainder cents to Amy, Mia.
        output = self.ok({
            "participants": ["Zed", "Amy", "Mia"],
            "expenses": [{"payer": "Zed", "amount": "100.01",
                          "split_type": "equal",
                          "participants": ["Zed", "Amy", "Mia"]}],
        })
        # owed: Amy 3334, Mia 3334, Zed 3333
        self.assertEqual(output["balances"],
                         {"Zed": 10001 - 3333, "Amy": -3334, "Mia": -3334})

    def test_payer_in_own_split(self):
        output = self.ok({
            "participants": ["A", "B"],
            "expenses": [{"payer": "A", "amount": "10.00",
                          "split_type": "equal", "participants": ["A", "B"]}],
        })
        self.assertEqual(output["balances"], {"A": 500, "B": -500})
        self.assertEqual(output["transfers"],
                         [{"from": "B", "to": "A", "amount_cents": 500}])

    def test_amounts_as_json_numbers_stay_exact(self):
        # 4.35 is the classic float trap: int(4.35 * 100) == 434 in binary
        # floating point. splitfair must produce 435.
        raw = ('{"participants": ["Al", "Bo"], "expenses": ['
               '{"payer": "Al", "amount": 4.35, "split_type": "exact",'
               ' "amounts": {"Bo": 4.35}}]}')
        output = self.ok(None, raw_text=raw)
        self.assertEqual(output["balances"], {"Al": 435, "Bo": -435})

    def test_percent_float_trap_sums_exactly(self):
        # 0.1 + 0.2 + 99.7 != 100 in binary floats; exactly 100 in decimal.
        raw = ('{"participants": ["A", "B", "C"], "expenses": ['
               '{"payer": "A", "amount": "30.00", "split_type": "percent",'
               ' "percents": {"A": 0.1, "B": 0.2, "C": 99.7}}]}')
        output = self.ok(None, raw_text=raw)
        self.assertEqual(sum(output["balances"].values()), 0)
        # C owes floor(3000 * 99.7/100) = floor(2991.0) = 2991
        self.assertEqual(output["balances"]["C"], -2991)

    def test_percent_more_than_two_decimals_allowed(self):
        output = self.ok({
            "participants": ["A", "B", "C"],
            "expenses": [{"payer": "A", "amount": "10.00",
                          "split_type": "percent",
                          "percents": {"A": "33.333", "B": "33.333",
                                       "C": "33.334"}}],
        })
        self.assertEqual(sum(output["balances"].values()), 0)

    def test_settlement_tie_breaks_alphabetical(self):
        output = self.ok({
            "participants": ["Ann", "Bea", "Cal", "Dee"],
            "expenses": [
                {"payer": "Ann", "amount": "5.00", "split_type": "exact",
                 "amounts": {"Cal": "5.00"}},
                {"payer": "Bea", "amount": "5.00", "split_type": "exact",
                 "amounts": {"Dee": "5.00"}},
            ],
        })
        # Debt ties (Cal, Dee) and credit ties (Ann, Bea): alphabetical first.
        self.assertEqual(output["transfers"], [
            {"from": "Cal", "to": "Ann", "amount_cents": 500},
            {"from": "Dee", "to": "Bea", "amount_cents": 500},
        ])

    def test_transfer_bound_and_settlement_zeroes(self):
        names = ["P%02d" % i for i in range(8)]
        expenses = []
        amounts = ["13.37", "99.99", "0.03", "45.67", "100.01", "7.77", "250.00"]
        for i, amt in enumerate(amounts):
            expenses.append({"payer": names[i % len(names)], "amount": amt,
                             "split_type": "equal", "participants": names})
        output = self.ok({"participants": names, "expenses": expenses})
        balances = dict(output["balances"])
        self.assertEqual(sum(balances.values()), 0)
        self.assertLessEqual(len(output["transfers"]), len(names) - 1)
        for t in output["transfers"]:
            self.assertGreater(t["amount_cents"], 0)
            balances[t["from"]] += t["amount_cents"]
            balances[t["to"]] -= t["amount_cents"]
        self.assertTrue(all(v == 0 for v in balances.values()),
                        "transfers must settle every balance to exactly zero")

    def test_balances_include_zero_balance_participant(self):
        output = self.ok({
            "participants": ["A", "B", "Idle"],
            "expenses": [{"payer": "A", "amount": "1.00",
                          "split_type": "exact", "amounts": {"B": "1.00"}}],
        })
        self.assertEqual(output["balances"], {"A": 100, "B": -100, "Idle": 0})
        self.assertEqual(len(output["transfers"]), 1)

    def test_integer_amount_accepted(self):
        output = self.ok({
            "participants": ["A", "B"],
            "expenses": [{"payer": "A", "amount": 7, "split_type": "exact",
                          "amounts": {"B": "7.00"}}],
        })
        self.assertEqual(output["balances"], {"A": 700, "B": -700})

    def test_large_amounts_no_overflow(self):
        output = self.ok({
            "participants": ["A", "B"],
            "expenses": [{"payer": "A", "amount": "99999999999999999.99",
                          "split_type": "exact",
                          "amounts": {"B": "99999999999999999.99"}}],
        })
        self.assertEqual(output["balances"]["A"], 9999999999999999999)


class TestRejections(CliCase):
    BASE = {"participants": ["Alice", "Bob"], "expenses": []}

    def expense(self, **kw):
        exp = {"payer": "Alice", "amount": "10.00", "split_type": "equal",
               "participants": ["Alice", "Bob"]}
        exp.update(kw)
        return {"participants": ["Alice", "Bob"], "expenses": [exp]}

    def test_malformed_json(self):
        self.rejected(None, raw_text='{"participants": ["A",]')

    def test_empty_file(self):
        self.rejected(None, raw_text="")

    def test_top_level_not_object(self):
        self.rejected(None, raw_text='["not", "an", "object"]')

    def test_missing_participants_key(self):
        self.rejected({"expenses": []})

    def test_missing_expenses_key(self):
        self.rejected({"participants": ["A"]})

    def test_empty_participants(self):
        self.rejected({"participants": [], "expenses": []})

    def test_duplicate_participants(self):
        self.rejected({"participants": ["A", "B", "A"], "expenses": []})

    def test_non_string_participant(self):
        self.rejected({"participants": ["A", 5], "expenses": []})

    def test_empty_string_participant(self):
        self.rejected({"participants": [""], "expenses": []})

    def test_unknown_payer(self):
        self.rejected(self.expense(payer="Mallory"))

    def test_unknown_name_in_split(self):
        self.rejected(self.expense(participants=["Alice", "Mallory"]))

    def test_zero_amount(self):
        self.rejected(self.expense(amount="0.00"))

    def test_negative_amount(self):
        self.rejected(self.expense(amount="-5.00"))

    def test_negative_number_amount(self):
        self.rejected(None, raw_text=json.dumps(self.expense(amount=-5)))

    def test_three_decimal_amount(self):
        self.rejected(self.expense(amount="10.005"))

    def test_exponent_amount(self):
        self.rejected(self.expense(amount="1e2"))

    def test_bare_dot_amount(self):
        self.rejected(self.expense(amount=".50"))

    def test_plus_sign_amount(self):
        self.rejected(self.expense(amount="+5.00"))

    def test_whitespace_amount(self):
        self.rejected(self.expense(amount=" 5.00"))

    def test_null_amount(self):
        self.rejected(self.expense(amount=None))

    def test_boolean_amount(self):
        self.rejected(self.expense(amount=True))

    def test_nan_amount(self):
        self.rejected(None, raw_text=(
            '{"participants": ["Alice"], "expenses": [{"payer": "Alice",'
            ' "amount": NaN, "split_type": "equal", "participants": ["Alice"]}]}'))

    def test_missing_amount(self):
        self.rejected({"participants": ["Alice"],
                       "expenses": [{"payer": "Alice", "split_type": "equal",
                                     "participants": ["Alice"]}]})

    def test_unknown_split_type(self):
        self.rejected(self.expense(split_type="evenly"))

    def test_missing_split_type(self):
        data = self.expense()
        del data["expenses"][0]["split_type"]
        self.rejected(data)

    def test_equal_empty_participants(self):
        self.rejected(self.expense(participants=[]))

    def test_equal_duplicate_participants(self):
        self.rejected(self.expense(participants=["Alice", "Alice"]))

    def test_shares_missing_field(self):
        self.rejected(self.expense(split_type="shares"))

    def test_shares_empty(self):
        self.rejected(self.expense(split_type="shares", shares={}))

    def test_shares_zero_weight(self):
        self.rejected(self.expense(split_type="shares",
                                   shares={"Alice": 0, "Bob": 1}))

    def test_shares_negative_weight(self):
        self.rejected(self.expense(split_type="shares",
                                   shares={"Alice": -1, "Bob": 2}))

    def test_shares_float_weight(self):
        self.rejected(None, raw_text=json.dumps(
            self.expense(split_type="shares", shares={"Alice": 1, "Bob": 2}))
            .replace('"Bob": 2', '"Bob": 2.0'))

    def test_shares_string_weight(self):
        self.rejected(self.expense(split_type="shares",
                                   shares={"Alice": "1", "Bob": 2}))

    def test_shares_boolean_weight(self):
        self.rejected(self.expense(split_type="shares",
                                   shares={"Alice": True, "Bob": 2}))

    def test_percent_sum_under_100(self):
        self.rejected(self.expense(split_type="percent",
                                   percents={"Alice": "50.00", "Bob": "49.99"}))

    def test_percent_sum_over_100(self):
        self.rejected(self.expense(split_type="percent",
                                   percents={"Alice": "50.00", "Bob": "50.01"}))

    def test_percent_negative(self):
        self.rejected(self.expense(split_type="percent",
                                   percents={"Alice": "-10", "Bob": "110"}))

    def test_percent_unknown_name(self):
        self.rejected(self.expense(split_type="percent",
                                   percents={"Alice": "50", "Eve": "50"}))

    def test_exact_sum_mismatch(self):
        self.rejected(self.expense(split_type="exact",
                                   amounts={"Bob": "9.99"}))

    def test_exact_three_decimals(self):
        self.rejected(self.expense(split_type="exact",
                                   amounts={"Bob": "10.000"}))

    def test_exact_negative_entry(self):
        self.rejected(self.expense(split_type="exact",
                                   amounts={"Alice": "-5.00", "Bob": "15.00"}))

    def test_duplicate_json_keys_in_shares(self):
        self.rejected(None, raw_text=(
            '{"participants": ["Alice", "Bob"], "expenses": [{"payer": "Alice",'
            ' "amount": "10.00", "split_type": "shares",'
            ' "shares": {"Bob": 1, "Bob": 2}}]}'))

    def test_expense_not_object(self):
        self.rejected({"participants": ["A"], "expenses": ["nope"]})

    def test_expenses_not_list(self):
        self.rejected({"participants": ["A"], "expenses": {}})

    def test_non_utf8_input_file(self):
        in_path = os.path.join(self.tmpdir, "input.json")
        out_path = os.path.join(self.tmpdir, "output.json")
        with open(in_path, "wb") as fh:
            fh.write(b"\xa5\xff\x00 not json")
        proc = subprocess.run([sys.executable, PROGRAM, in_path, out_path],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("invalid input", proc.stderr)
        self.assertFalse(os.path.exists(out_path))

    def test_unicode_names_roundtrip(self):
        code, stderr, output, _ = run_cli({
            "participants": ["Zoë", "émile"],
            "expenses": [{"payer": "Zoë", "amount": "0.03",
                          "split_type": "equal",
                          "participants": ["Zoë", "émile"]}],
        }, self.tmpdir)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(output["balances"], {"Zoë": 1, "émile": -1})

    def test_input_file_missing(self):
        out_path = os.path.join(self.tmpdir, "output.json")
        proc = subprocess.run(
            [sys.executable, PROGRAM,
             os.path.join(self.tmpdir, "no-such-file.json"), out_path],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(proc.stderr.strip())
        self.assertFalse(os.path.exists(out_path))


class TestCliContract(unittest.TestCase):
    def test_wrong_arg_count(self):
        for args in ([], ["only-one.json"], ["a.json", "b.json", "c.json"]):
            proc = subprocess.run([sys.executable, PROGRAM] + args,
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("usage", proc.stderr)

    def test_unwritable_output_exits_1(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = os.path.join(tmpdir, "input.json")
            with open(in_path, "w", encoding="utf-8") as fh:
                json.dump({"participants": ["A"], "expenses": []}, fh)
            out_path = os.path.join(tmpdir, "no-such-dir", "out.json")
            proc = subprocess.run([sys.executable, PROGRAM, in_path, out_path],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1)
            self.assertTrue(proc.stderr.strip())


class TestUnits(unittest.TestCase):
    def test_money_to_cents(self):
        cases = {"0.01": 1, "1": 100, "1.5": 150, "1.50": 150,
                 "100.00": 10000, "007": 700}
        for text, cents in cases.items():
            self.assertEqual(splitfair.money_to_cents(text, "t"), cents)

    def test_money_to_cents_rejects(self):
        for bad in ["", ".", "1.", ".5", "1.234", "1e2", "-1", "+1", "1,00",
                    "1 ", "0x10", "NaN", "Infinity"]:
            with self.assertRaises(splitfair.InputError, msg=bad):
                splitfair.money_to_cents(bad, "t")

    def test_allocate_floor_and_alphabetical_remainder(self):
        # 100 cents by shares {X:1, A:1, M:1} -> 33 each, remainder 1 -> A.
        self.assertEqual(splitfair.allocate(100, {"X": 1, "A": 1, "M": 1}),
                         {"A": 34, "M": 33, "X": 33})
        # remainder 2 -> A and M.
        self.assertEqual(splitfair.allocate(200, {"X": 1, "A": 1, "M": 1}),
                         {"A": 67, "M": 67, "X": 66})

    def test_allocate_conserves_total(self):
        for total in (0, 1, 7, 99, 10001):
            for weights in ({"a": 1, "b": 2, "c": 3}, {"a": 7},
                            {"a": 3, "b": 3, "c": 3, "d": 1}):
                self.assertEqual(sum(splitfair.allocate(total, weights).values()),
                                 total)

    def test_settle_empty_when_all_zero(self):
        self.assertEqual(splitfair.settle({"a": 0, "b": 0}), [])


if __name__ == "__main__":
    unittest.main()
