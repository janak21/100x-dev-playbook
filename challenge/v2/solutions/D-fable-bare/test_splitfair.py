#!/usr/bin/env python3
"""Automated tests for splitfair.

Run:  python3 -m unittest discover -v
  or: python3 test_splitfair.py
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import tempfile
import time
import unittest
from decimal import Decimal
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "splitfair.py")

sys.path.insert(0, HERE)
import splitfair  # noqa: E402


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def run_cli(payload, *, raw=None):
    """Run the CLI on `payload` (or `raw` text) and return (rc, out, stderr)."""
    tmpdir = tempfile.mkdtemp()
    in_path = os.path.join(tmpdir, "input.json")
    out_path = os.path.join(tmpdir, "output.json")
    text = raw if raw is not None else json.dumps(payload)
    with open(in_path, "w", encoding="utf-8") as handle:
        handle.write(text)

    proc = subprocess.run(
        [sys.executable, SCRIPT, in_path, out_path],
        capture_output=True,
        text=True,
    )
    result = None
    if os.path.exists(out_path):
        with open(out_path, "r", encoding="utf-8") as handle:
            result = handle.read()
    return proc.returncode, result, proc.stderr


class SplitfairCase(unittest.TestCase):
    def ok(self, payload):
        rc, out, err = run_cli(payload)
        self.assertEqual(rc, 0, "expected success, stderr=%s" % err)
        self.assertIsNotNone(out, "expected an output file")
        return json.loads(out)

    def rejects(self, payload, *, raw=None):
        rc, out, err = run_cli(payload, raw=raw)
        self.assertEqual(rc, 1, "expected exit 1, got %d (out=%s)" % (rc, out))
        self.assertIsNone(out, "invalid input must not write an output file")
        self.assertTrue(err.strip(), "expected a message on stderr")
        return err

    def check_invariants(self, payload, result):
        """Every property the spec demands, checked against the output."""
        names = payload["participants"]
        balances = result["balances"]

        # Requirement 1: balances cover everyone and sum to exactly zero.
        self.assertEqual(sorted(balances.keys()), sorted(names))
        for value in balances.values():
            self.assertIsInstance(value, int)
            self.assertNotIsInstance(value, bool)
        self.assertEqual(sum(balances.values()), 0)

        # Requirement 3: at most n-1 transfers, all strictly positive.
        transfers = result["transfers"]
        self.assertLessEqual(max(len(names) - 1, 0), max(len(names) - 1, 0))
        self.assertLessEqual(len(transfers), max(len(names) - 1, 0))
        for transfer in transfers:
            self.assertGreater(transfer["amount_cents"], 0)
            self.assertIn(transfer["from"], balances)
            self.assertIn(transfer["to"], balances)
            self.assertNotEqual(transfer["from"], transfer["to"])

        # The plan actually settles everyone: applying it zeroes all balances.
        net = dict(balances)
        for transfer in transfers:
            net[transfer["from"]] += transfer["amount_cents"]
            net[transfer["to"]] -= transfer["amount_cents"]
        self.assertTrue(
            all(value == 0 for value in net.values()),
            "transfers did not settle everyone: %s" % net,
        )


# --------------------------------------------------------------------------
# Core behaviour
# --------------------------------------------------------------------------


class TestBasics(SplitfairCase):
    def test_equal_split_clean(self):
        payload = {
            "participants": ["Ana", "Bob"],
            "expenses": [
                {
                    "payer": "Ana",
                    "amount": "10.00",
                    "split_type": "equal",
                    "participants": ["Ana", "Bob"],
                }
            ],
        }
        result = self.ok(payload)
        self.assertEqual(result["balances"], {"Ana": 500, "Bob": -500})
        self.assertEqual(
            result["transfers"], [{"from": "Bob", "to": "Ana", "amount_cents": 500}]
        )
        self.check_invariants(payload, result)

    def test_equal_split_indivisible_penny(self):
        """10.00 across 3 people: 334/333/333, never 333/333/333."""
        payload = {
            "participants": ["Ana", "Bob", "Cy"],
            "expenses": [
                {
                    "payer": "Ana",
                    "amount": "10.00",
                    "split_type": "equal",
                    "participants": ["Ana", "Bob", "Cy"],
                }
            ],
        }
        result = self.ok(payload)
        shares = {"Ana": 1000 - result["balances"]["Ana"], "Bob": -result["balances"]["Bob"],
                  "Cy": -result["balances"]["Cy"]}
        self.assertEqual(sum(shares.values()), 1000)
        for value in shares.values():
            self.assertIn(value, (333, 334))
        self.check_invariants(payload, result)

    def test_one_cent_across_three(self):
        payload = {
            "participants": ["Ana", "Bob", "Cy"],
            "expenses": [
                {
                    "payer": "Ana",
                    "amount": "0.01",
                    "split_type": "equal",
                    "participants": ["Ana", "Bob", "Cy"],
                }
            ],
        }
        result = self.ok(payload)
        self.assertEqual(sum(result["balances"].values()), 0)
        self.check_invariants(payload, result)

    def test_shares_split(self):
        payload = {
            "participants": ["Ana", "Bob"],
            "expenses": [
                {
                    "payer": "Ana",
                    "amount": "10.00",
                    "split_type": "shares",
                    "shares": {"Ana": 1, "Bob": 3},
                }
            ],
        }
        result = self.ok(payload)
        self.assertEqual(result["balances"], {"Ana": 750, "Bob": -750})
        self.check_invariants(payload, result)

    def test_shares_with_zero_weight(self):
        payload = {
            "participants": ["Ana", "Bob"],
            "expenses": [
                {
                    "payer": "Ana",
                    "amount": "10.00",
                    "split_type": "shares",
                    "shares": {"Ana": 0, "Bob": 1},
                }
            ],
        }
        result = self.ok(payload)
        self.assertEqual(result["balances"], {"Ana": 1000, "Bob": -1000})

    def test_percent_split(self):
        payload = {
            "participants": ["Ana", "Bob"],
            "expenses": [
                {
                    "payer": "Ana",
                    "amount": "12.34",
                    "split_type": "percent",
                    "percents": {"Ana": "33.33", "Bob": "66.67"},
                }
            ],
        }
        result = self.ok(payload)
        self.assertEqual(sum(result["balances"].values()), 0)
        # Ana's exact share is 12.34 * 0.3333 = 411.29...  cents.
        ana_share = 1234 - result["balances"]["Ana"]
        self.assertIn(ana_share, (411, 412))
        self.check_invariants(payload, result)

    def test_exact_split(self):
        payload = {
            "participants": ["Ana", "Bob"],
            "expenses": [
                {
                    "payer": "Ana",
                    "amount": "12.34",
                    "split_type": "exact",
                    "amounts": {"Ana": "4.00", "Bob": "8.34"},
                }
            ],
        }
        result = self.ok(payload)
        self.assertEqual(result["balances"], {"Ana": 834, "Bob": -834})

    def test_payer_outside_split(self):
        payload = {
            "participants": ["Ana", "Bob", "Cy"],
            "expenses": [
                {
                    "payer": "Cy",
                    "amount": "10.00",
                    "split_type": "equal",
                    "participants": ["Ana", "Bob"],
                }
            ],
        }
        result = self.ok(payload)
        self.assertEqual(result["balances"], {"Ana": -500, "Bob": -500, "Cy": 1000})
        self.check_invariants(payload, result)

    def test_zero_amount(self):
        payload = {
            "participants": ["Ana", "Bob"],
            "expenses": [
                {
                    "payer": "Ana",
                    "amount": "0.00",
                    "split_type": "equal",
                    "participants": ["Ana", "Bob"],
                }
            ],
        }
        result = self.ok(payload)
        self.assertEqual(result["balances"], {"Ana": 0, "Bob": 0})
        self.assertEqual(result["transfers"], [])

    def test_no_expenses(self):
        payload = {"participants": ["Ana", "Bob"], "expenses": []}
        result = self.ok(payload)
        self.assertEqual(result["balances"], {"Ana": 0, "Bob": 0})
        self.assertEqual(result["transfers"], [])

    def test_no_participants_no_expenses(self):
        payload = {"participants": [], "expenses": []}
        result = self.ok(payload)
        self.assertEqual(result, {"balances": {}, "transfers": []})

    def test_single_participant(self):
        payload = {
            "participants": ["Ana"],
            "expenses": [
                {
                    "payer": "Ana",
                    "amount": "5.00",
                    "split_type": "equal",
                    "participants": ["Ana"],
                }
            ],
        }
        result = self.ok(payload)
        self.assertEqual(result["balances"], {"Ana": 0})
        self.assertEqual(result["transfers"], [])

    def test_unicode_names_round_trip(self):
        payload = {
            "participants": ["Ána", "日本", "Bob"],
            "expenses": [
                {
                    "payer": "日本",
                    "amount": "9.00",
                    "split_type": "equal",
                    "participants": ["Ána", "日本", "Bob"],
                }
            ],
        }
        result = self.ok(payload)
        self.assertEqual(result["balances"]["日本"], 600)
        self.check_invariants(payload, result)

    def test_large_amount(self):
        payload = {
            "participants": ["Ana", "Bob"],
            "expenses": [
                {
                    "payer": "Ana",
                    "amount": "99999999999999999999.99",
                    "split_type": "equal",
                    "participants": ["Ana", "Bob"],
                }
            ],
        }
        result = self.ok(payload)
        self.assertEqual(sum(result["balances"].values()), 0)
        self.check_invariants(payload, result)


# --------------------------------------------------------------------------
# Fairness to the cent
# --------------------------------------------------------------------------


class TestFairness(SplitfairCase):
    def assert_within_a_cent(self, total_cents, weights):
        order = list(range(len(weights)))
        alloc = splitfair.allocate(total_cents, weights, order)
        self.assertEqual(sum(alloc), total_cents, "allocation must be exact")
        # Fractions, not Decimals: the reference value must be exact too.
        fracs = [Fraction(weight) for weight in weights]
        total_weight = sum(fracs)
        for i, share in enumerate(alloc):
            exact = Fraction(total_cents) * fracs[i] / total_weight
            self.assertLess(
                abs(Fraction(share) - exact),
                1,
                "share %d off by >= 1 cent (got %d, exact %s)" % (i, share, exact),
            )

    def test_equal_splits_are_fair(self):
        for n in range(1, 60):
            for total in (0, 1, 7, 99, 100, 101, 12345, 999999):
                self.assert_within_a_cent(total, [Decimal(1)] * n)

    def test_random_weights_are_fair(self):
        rng = random.Random(20260721)
        for _ in range(400):
            n = rng.randint(1, 40)
            weights = [Decimal(rng.randint(0, 500)) for _ in range(n)]
            if sum(weights) == 0:
                weights[0] = Decimal(1)
            total = rng.randint(0, 5_000_000)
            self.assert_within_a_cent(total, weights)

    def test_fractional_weights_are_fair(self):
        rng = random.Random(7)
        for _ in range(200):
            n = rng.randint(2, 20)
            weights = [
                Decimal(rng.randint(1, 100000)).scaleb(-3) for _ in range(n)
            ]
            total = rng.randint(0, 1_000_000)
            self.assert_within_a_cent(total, weights)

    def test_pathological_percent_thirds(self):
        payload = {
            "participants": ["A", "B", "C"],
            "expenses": [
                {
                    "payer": "A",
                    "amount": "100.00",
                    "split_type": "percent",
                    "percents": {
                        "A": "33.333333333333333333333333333333",
                        "B": "33.333333333333333333333333333333",
                        "C": "33.333333333333333333333333333334",
                    },
                }
            ],
        }
        result = self.ok(payload)
        self.assertEqual(sum(result["balances"].values()), 0)
        self.check_invariants(payload, result)


# --------------------------------------------------------------------------
# Settlement properties
# --------------------------------------------------------------------------


class TestSettlement(SplitfairCase):
    def test_transfer_bound_random(self):
        rng = random.Random(4242)
        for trial in range(150):
            n = rng.randint(2, 25)
            names = ["P%02d" % i for i in range(n)]
            expenses = []
            for _ in range(rng.randint(1, 30)):
                members = rng.sample(names, rng.randint(1, n))
                expenses.append(
                    {
                        "payer": rng.choice(names),
                        "amount": "%d.%02d" % (rng.randint(0, 900), rng.randint(0, 99)),
                        "split_type": "equal",
                        "participants": members,
                    }
                )
            payload = {"participants": names, "expenses": expenses}
            result = self.ok(payload)
            self.check_invariants(payload, result)

    def test_settle_unit(self):
        names = ["a", "b", "c", "d"]
        balances = [100, -30, -30, -40]
        transfers = splitfair.settle(names, balances)
        self.assertLessEqual(len(transfers), 3)
        self.assertTrue(all(t["amount_cents"] > 0 for t in transfers))

    def test_settle_all_zero(self):
        self.assertEqual(splitfair.settle(["a", "b"], [0, 0]), [])

    def test_worst_case_chain(self):
        """n-1 creditors and n-1 debtors, all one cent -- still <= n-1."""
        n = 30
        names = ["P%02d" % i for i in range(n)]
        balances = [0] * n
        for i in range(n // 2):
            balances[i] = 1
            balances[n // 2 + i] = -1
        transfers = splitfair.settle(names, balances)
        self.assertLessEqual(len(transfers), n - 1)


# --------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------


class TestDeterminism(SplitfairCase):
    def test_byte_identical_across_runs(self):
        rng = random.Random(99)
        names = ["N%02d" % i for i in range(12)]
        expenses = []
        for _ in range(60):
            kind = rng.choice(["equal", "shares", "percent"])
            members = rng.sample(names, rng.randint(1, 6))
            expense = {
                "payer": rng.choice(names),
                "amount": "%d.%02d" % (rng.randint(1, 400), rng.randint(0, 99)),
                "split_type": kind,
            }
            if kind == "equal":
                expense["participants"] = members
            elif kind == "shares":
                expense["shares"] = {m: rng.randint(0, 9) or 1 for m in members}
            else:
                pcts = [Decimal(0)] * len(members)
                left = Decimal(100)
                for i in range(len(members) - 1):
                    take = (left / (len(members) - i)).quantize(Decimal("0.01"))
                    pcts[i] = take
                    left -= take
                pcts[-1] = left
                expense["percents"] = {
                    m: format(p, "f") for m, p in zip(members, pcts)
                }
            expenses.append(expense)
        payload = {"participants": names, "expenses": expenses}

        outputs = set()
        for _ in range(4):
            rc, out, err = run_cli(payload)
            self.assertEqual(rc, 0, err)
            outputs.add(out)
        self.assertEqual(len(outputs), 1, "output was not byte-identical")

    def test_key_order_in_input_does_not_matter(self):
        base = {
            "participants": ["Ana", "Bob", "Cy"],
            "expenses": [
                {
                    "payer": "Ana",
                    "amount": "10.00",
                    "split_type": "shares",
                    "shares": {"Ana": 1, "Bob": 1, "Cy": 1},
                }
            ],
        }
        reordered = json.loads(json.dumps(base))
        reordered["expenses"][0]["shares"] = {"Cy": 1, "Bob": 1, "Ana": 1}
        self.assertEqual(self.ok(base), self.ok(reordered))

    def test_balances_follow_participant_order(self):
        payload = {
            "participants": ["Zed", "Ana", "Mel"],
            "expenses": [
                {
                    "payer": "Zed",
                    "amount": "3.00",
                    "split_type": "equal",
                    "participants": ["Zed", "Ana", "Mel"],
                }
            ],
        }
        rc, out, err = run_cli(payload)
        self.assertEqual(rc, 0, err)
        self.assertEqual(list(json.loads(out)["balances"].keys()), ["Zed", "Ana", "Mel"])


# --------------------------------------------------------------------------
# Invalid input
# --------------------------------------------------------------------------


class TestInvalidInput(SplitfairCase):
    def test_not_json(self):
        self.rejects(None, raw="{not json")

    def test_empty_file(self):
        self.rejects(None, raw="")

    def test_top_level_array(self):
        self.rejects([1, 2, 3])

    def test_top_level_null(self):
        self.rejects(None)

    def test_missing_participants(self):
        self.rejects({"expenses": []})

    def test_missing_expenses(self):
        self.rejects({"participants": ["Ana"]})

    def test_participants_not_array(self):
        self.rejects({"participants": {"Ana": 1}, "expenses": []})

    def test_duplicate_participant(self):
        self.rejects({"participants": ["Ana", "Ana"], "expenses": []})

    def test_empty_name(self):
        self.rejects({"participants": [""], "expenses": []})

    def test_non_string_name(self):
        self.rejects({"participants": [5], "expenses": []})

    def test_expenses_not_array(self):
        self.rejects({"participants": ["Ana"], "expenses": {}})

    def test_expense_not_object(self):
        self.rejects({"participants": ["Ana"], "expenses": ["nope"]})

    def test_unknown_payer(self):
        self.rejects(
            {
                "participants": ["Ana"],
                "expenses": [
                    {
                        "payer": "Ghost",
                        "amount": "1.00",
                        "split_type": "equal",
                        "participants": ["Ana"],
                    }
                ],
            }
        )

    def test_unknown_split_member(self):
        self.rejects(
            {
                "participants": ["Ana"],
                "expenses": [
                    {
                        "payer": "Ana",
                        "amount": "1.00",
                        "split_type": "equal",
                        "participants": ["Ana", "Ghost"],
                    }
                ],
            }
        )

    def test_unknown_split_type(self):
        self.rejects(
            {
                "participants": ["Ana"],
                "expenses": [
                    {"payer": "Ana", "amount": "1.00", "split_type": "weighted"}
                ],
            }
        )

    def test_amount_as_number(self):
        self.rejects(
            {
                "participants": ["Ana"],
                "expenses": [
                    {
                        "payer": "Ana",
                        "amount": 1.0,
                        "split_type": "equal",
                        "participants": ["Ana"],
                    }
                ],
            }
        )

    def test_amount_negative(self):
        self.rejects(
            {
                "participants": ["Ana"],
                "expenses": [
                    {
                        "payer": "Ana",
                        "amount": "-1.00",
                        "split_type": "equal",
                        "participants": ["Ana"],
                    }
                ],
            }
        )

    def test_amount_sub_cent(self):
        self.rejects(
            {
                "participants": ["Ana"],
                "expenses": [
                    {
                        "payer": "Ana",
                        "amount": "1.005",
                        "split_type": "equal",
                        "participants": ["Ana"],
                    }
                ],
            }
        )

    def test_amount_exponent_notation(self):
        self.rejects(
            {
                "participants": ["Ana"],
                "expenses": [
                    {
                        "payer": "Ana",
                        "amount": "1e2",
                        "split_type": "equal",
                        "participants": ["Ana"],
                    }
                ],
            }
        )

    def test_amount_nan_string(self):
        for bad in ("NaN", "Infinity", "-Infinity", "0x10", " 1.00", "1.00 ", "", "."):
            self.rejects(
                {
                    "participants": ["Ana"],
                    "expenses": [
                        {
                            "payer": "Ana",
                            "amount": bad,
                            "split_type": "equal",
                            "participants": ["Ana"],
                        }
                    ],
                }
            )

    def test_json_nan_literal(self):
        self.rejects(
            None,
            raw='{"participants":["Ana"],"expenses":[{"payer":"Ana","amount":NaN,'
                '"split_type":"equal","participants":["Ana"]}]}',
        )

    def test_duplicate_json_key(self):
        self.rejects(
            None,
            raw='{"participants":["Ana","Bob"],"participants":["Ana"],"expenses":[]}',
        )

    def test_duplicate_key_in_shares(self):
        self.rejects(
            None,
            raw='{"participants":["Ana","Bob"],"expenses":[{"payer":"Ana",'
                '"amount":"2.00","split_type":"shares","shares":{"Ana":1,"Ana":3}}]}',
        )

    def test_equal_empty_member_list(self):
        self.rejects(
            {
                "participants": ["Ana"],
                "expenses": [
                    {
                        "payer": "Ana",
                        "amount": "1.00",
                        "split_type": "equal",
                        "participants": [],
                    }
                ],
            }
        )

    def test_equal_duplicate_member(self):
        self.rejects(
            {
                "participants": ["Ana", "Bob"],
                "expenses": [
                    {
                        "payer": "Ana",
                        "amount": "1.00",
                        "split_type": "equal",
                        "participants": ["Ana", "Ana"],
                    }
                ],
            }
        )

    def test_equal_missing_member_list(self):
        self.rejects(
            {
                "participants": ["Ana"],
                "expenses": [
                    {"payer": "Ana", "amount": "1.00", "split_type": "equal"}
                ],
            }
        )

    def test_shares_all_zero(self):
        self.rejects(
            {
                "participants": ["Ana", "Bob"],
                "expenses": [
                    {
                        "payer": "Ana",
                        "amount": "1.00",
                        "split_type": "shares",
                        "shares": {"Ana": 0, "Bob": 0},
                    }
                ],
            }
        )

    def test_shares_negative(self):
        self.rejects(
            {
                "participants": ["Ana", "Bob"],
                "expenses": [
                    {
                        "payer": "Ana",
                        "amount": "1.00",
                        "split_type": "shares",
                        "shares": {"Ana": -1, "Bob": 3},
                    }
                ],
            }
        )

    def test_shares_float(self):
        self.rejects(
            {
                "participants": ["Ana", "Bob"],
                "expenses": [
                    {
                        "payer": "Ana",
                        "amount": "1.00",
                        "split_type": "shares",
                        "shares": {"Ana": 1.5, "Bob": 3},
                    }
                ],
            }
        )

    def test_shares_boolean(self):
        self.rejects(
            {
                "participants": ["Ana", "Bob"],
                "expenses": [
                    {
                        "payer": "Ana",
                        "amount": "1.00",
                        "split_type": "shares",
                        "shares": {"Ana": True, "Bob": 3},
                    }
                ],
            }
        )

    def test_shares_empty(self):
        self.rejects(
            {
                "participants": ["Ana"],
                "expenses": [
                    {
                        "payer": "Ana",
                        "amount": "1.00",
                        "split_type": "shares",
                        "shares": {},
                    }
                ],
            }
        )

    def test_percent_not_100(self):
        for pcts in (
            {"Ana": "50.00", "Bob": "49.99"},
            {"Ana": "50.00", "Bob": "50.01"},
            {"Ana": "100.00", "Bob": "0.01"},
        ):
            self.rejects(
                {
                    "participants": ["Ana", "Bob"],
                    "expenses": [
                        {
                            "payer": "Ana",
                            "amount": "1.00",
                            "split_type": "percent",
                            "percents": pcts,
                        }
                    ],
                }
            )

    def test_percent_long_digits_just_under_100(self):
        """Precision trap: 33.33...3 x 3 = 99.99...9, must NOT be accepted.

        Decimal's default 28-digit context would round this to exactly 100.
        """
        third = "33." + "3" * 40
        self.rejects(
            {
                "participants": ["A", "B", "C"],
                "expenses": [
                    {
                        "payer": "A",
                        "amount": "100.00",
                        "split_type": "percent",
                        "percents": {"A": third, "B": third, "C": third},
                    }
                ],
            }
        )

    def test_amount_long_digits_sub_cent(self):
        """Precision trap: a 40-digit amount with a stray sub-cent digit."""
        self.rejects(
            {
                "participants": ["Ana"],
                "expenses": [
                    {
                        "payer": "Ana",
                        "amount": "1" * 30 + ".001",
                        "split_type": "equal",
                        "participants": ["Ana"],
                    }
                ],
            }
        )

    def test_percent_negative(self):
        self.rejects(
            {
                "participants": ["Ana", "Bob"],
                "expenses": [
                    {
                        "payer": "Ana",
                        "amount": "1.00",
                        "split_type": "percent",
                        "percents": {"Ana": "-10.00", "Bob": "110.00"},
                    }
                ],
            }
        )

    def test_percent_sums_to_100_with_extra_precision(self):
        payload = {
            "participants": ["Ana", "Bob", "Cy"],
            "expenses": [
                {
                    "payer": "Ana",
                    "amount": "1.00",
                    "split_type": "percent",
                    "percents": {"Ana": "33.3", "Bob": "33.3", "Cy": "33.4"},
                }
            ],
        }
        self.check_invariants(payload, self.ok(payload))

    def test_exact_does_not_sum(self):
        self.rejects(
            {
                "participants": ["Ana", "Bob"],
                "expenses": [
                    {
                        "payer": "Ana",
                        "amount": "12.34",
                        "split_type": "exact",
                        "amounts": {"Ana": "4.00", "Bob": "8.33"},
                    }
                ],
            }
        )

    def test_exact_negative_component(self):
        self.rejects(
            {
                "participants": ["Ana", "Bob"],
                "expenses": [
                    {
                        "payer": "Ana",
                        "amount": "10.00",
                        "split_type": "exact",
                        "amounts": {"Ana": "-1.00", "Bob": "11.00"},
                    }
                ],
            }
        )

    def test_exact_sub_cent_component(self):
        self.rejects(
            {
                "participants": ["Ana", "Bob"],
                "expenses": [
                    {
                        "payer": "Ana",
                        "amount": "10.00",
                        "split_type": "exact",
                        "amounts": {"Ana": "5.005", "Bob": "4.995"},
                    }
                ],
            }
        )

    def test_split_data_not_object(self):
        self.rejects(
            {
                "participants": ["Ana"],
                "expenses": [
                    {
                        "payer": "Ana",
                        "amount": "1.00",
                        "split_type": "shares",
                        "shares": [1],
                    }
                ],
            }
        )

    def test_deeply_nested_json(self):
        raw = "[" * 200000 + "]" * 200000
        rc, out, err = run_cli(None, raw=raw)
        self.assertEqual(rc, 1)
        self.assertIsNone(out)

    def test_missing_input_file(self):
        tmpdir = tempfile.mkdtemp()
        proc = subprocess.run(
            [sys.executable, SCRIPT,
             os.path.join(tmpdir, "nope.json"), os.path.join(tmpdir, "out.json")],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(proc.stderr.strip())
        self.assertFalse(os.path.exists(os.path.join(tmpdir, "out.json")))

    def test_wrong_argument_count(self):
        for args in ([], ["a"], ["a", "b", "c"]):
            proc = subprocess.run(
                [sys.executable, SCRIPT] + args, capture_output=True, text=True
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("usage", proc.stderr.lower())

    def test_no_output_left_behind_on_late_error(self):
        """A bad expense at the end must still leave zero output files."""
        payload = {
            "participants": ["Ana", "Bob"],
            "expenses": [
                {
                    "payer": "Ana",
                    "amount": "1.00",
                    "split_type": "equal",
                    "participants": ["Ana", "Bob"],
                },
                {"payer": "Ana", "amount": "1.00", "split_type": "bogus"},
            ],
        }
        self.rejects(payload)


# --------------------------------------------------------------------------
# Extra keys are tolerated
# --------------------------------------------------------------------------


class TestTolerance(SplitfairCase):
    def test_unknown_keys_ignored(self):
        payload = {
            "participants": ["Ana", "Bob"],
            "currency": "EUR",
            "expenses": [
                {
                    "payer": "Ana",
                    "amount": "10.00",
                    "split_type": "equal",
                    "participants": ["Ana", "Bob"],
                    "note": "dinner",
                    "shares": {"Ana": 99},
                }
            ],
        }
        result = self.ok(payload)
        self.assertEqual(result["balances"], {"Ana": 500, "Bob": -500})

    def test_participant_with_no_expenses(self):
        payload = {
            "participants": ["Ana", "Bob", "Idle"],
            "expenses": [
                {
                    "payer": "Ana",
                    "amount": "10.00",
                    "split_type": "equal",
                    "participants": ["Ana", "Bob"],
                }
            ],
        }
        result = self.ok(payload)
        self.assertEqual(result["balances"]["Idle"], 0)
        self.check_invariants(payload, result)


# --------------------------------------------------------------------------
# Scale
# --------------------------------------------------------------------------


class TestPerformance(SplitfairCase):
    def test_50_participants_5000_expenses(self):
        rng = random.Random(2026)
        names = ["Person%02d" % i for i in range(50)]
        expenses = []
        for i in range(5000):
            kind = ("equal", "shares", "percent", "exact")[i % 4]
            members = rng.sample(names, rng.randint(2, 50))
            amount_cents = rng.randint(1, 500000)
            amount = "%d.%02d" % (amount_cents // 100, amount_cents % 100)
            expense = {
                "payer": rng.choice(names),
                "amount": amount,
                "split_type": kind,
            }
            if kind == "equal":
                expense["participants"] = members
            elif kind == "shares":
                expense["shares"] = {m: rng.randint(1, 10) for m in members}
            elif kind == "percent":
                pcts = []
                left = Decimal(100)
                for k in range(len(members) - 1):
                    take = (left / (len(members) - k)).quantize(Decimal("0.0001"))
                    pcts.append(take)
                    left -= take
                pcts.append(left)
                expense["percents"] = {
                    m: format(p, "f") for m, p in zip(members, pcts)
                }
            else:
                per = amount_cents // len(members)
                amounts = [per] * len(members)
                amounts[0] += amount_cents - per * len(members)
                expense["amounts"] = {
                    m: "%d.%02d" % (c // 100, c % 100)
                    for m, c in zip(members, amounts)
                }
            expenses.append(expense)

        payload = {"participants": names, "expenses": expenses}
        start = time.time()
        rc, out, err = run_cli(payload)
        elapsed = time.time() - start
        self.assertEqual(rc, 0, err)
        result = json.loads(out)
        self.check_invariants(payload, result)
        self.assertLess(elapsed, 10.0, "took %.2fs, budget is 10s" % elapsed)
        print("\n  [perf] 50 participants x 5000 expenses: %.2fs" % elapsed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
