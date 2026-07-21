"""
Comprehensive test suite for splitfair.

Tests cover:
- Input validation (schema, types, constraints)
- All split types (equal, shares, percent, exact)
- Fairness (no participant unfairly bears >1 cent of rounding error)
- Settlement (≤n-1 transfers, all positive)
- Determinism (same input → byte-identical output)
- Edge cases and adversarial inputs

Run with: python3 -m unittest tests.test_splitfair -v
"""

import json
import os
import subprocess
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

# Import the module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from splitfair import (
    validate_and_load_input,
    allocate_expense,
    compute_balances,
    settle_balances,
)


class TestInputValidation(unittest.TestCase):
    """Test input validation and rejection."""

    def test_valid_input_minimal(self):
        """Test minimal valid input."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            inp = {
                "participants": ["Alice", "Bob"],
                "expenses": [
                    {
                        "payer": "Alice",
                        "amount": "10.00",
                        "split_type": "equal",
                        "participants": ["Alice", "Bob"]
                    }
                ]
            }
            input_file = os.path.join(tmp_dir, "input.json")
            with open(input_file, 'w') as f:
                json.dump(inp, f)

            participants, expenses = validate_and_load_input(input_file)
            self.assertEqual(participants, ["Alice", "Bob"])
            self.assertEqual(len(expenses), 1)

    def test_missing_participants_field(self):
        """Test rejection when participants field is missing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            inp = {"expenses": []}
            input_file = os.path.join(tmp_dir, "input.json")
            with open(input_file, 'w') as f:
                json.dump(inp, f)

            with self.assertRaises(ValueError) as ctx:
                validate_and_load_input(input_file)
            self.assertIn("participants", str(ctx.exception))

    def test_missing_expenses_field(self):
        """Test rejection when expenses field is missing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            inp = {"participants": ["Alice"]}
            input_file = os.path.join(tmp_dir, "input.json")
            with open(input_file, 'w') as f:
                json.dump(inp, f)

            with self.assertRaises(ValueError) as ctx:
                validate_and_load_input(input_file)
            self.assertIn("expenses", str(ctx.exception))

    def test_empty_participants(self):
        """Test rejection of empty participants list."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            inp = {"participants": [], "expenses": []}
            input_file = os.path.join(tmp_dir, "input.json")
            with open(input_file, 'w') as f:
                json.dump(inp, f)

            with self.assertRaises(ValueError) as ctx:
                validate_and_load_input(input_file)
            self.assertIn("empty", str(ctx.exception))

    def test_empty_expenses_list(self):
        """Test rejection of empty expenses list."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            inp = {"participants": ["Alice"], "expenses": []}
            input_file = os.path.join(tmp_dir, "input.json")
            with open(input_file, 'w') as f:
                json.dump(inp, f)

            with self.assertRaises(ValueError) as ctx:
                validate_and_load_input(input_file)
            self.assertIn("empty", str(ctx.exception))

    def test_duplicate_participants(self):
        """Test rejection of duplicate participant names."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            inp = {"participants": ["Alice", "Bob", "Alice"], "expenses": []}
            input_file = os.path.join(tmp_dir, "input.json")
            with open(input_file, 'w') as f:
                json.dump(inp, f)

            with self.assertRaises(ValueError) as ctx:
                validate_and_load_input(input_file)
            self.assertIn("duplicate", str(ctx.exception))

    def test_payer_not_in_participants(self):
        """Test rejection when payer is not in participants list."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            inp = {
                "participants": ["Alice"],
                "expenses": [
                    {
                        "payer": "Charlie",
                        "amount": "10.00",
                        "split_type": "equal",
                        "participants": ["Alice"]
                    }
                ]
            }
            input_file = os.path.join(tmp_dir, "input.json")
            with open(input_file, 'w') as f:
                json.dump(inp, f)

            with self.assertRaises(ValueError) as ctx:
                validate_and_load_input(input_file)
            self.assertIn("payer", str(ctx.exception))

    def test_split_participant_not_in_participants(self):
        """Test rejection when split references unknown participant."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            inp = {
                "participants": ["Alice", "Bob"],
                "expenses": [
                    {
                        "payer": "Alice",
                        "amount": "10.00",
                        "split_type": "equal",
                        "participants": ["Alice", "Charlie"]
                    }
                ]
            }
            input_file = os.path.join(tmp_dir, "input.json")
            with open(input_file, 'w') as f:
                json.dump(inp, f)

            with self.assertRaises(ValueError) as ctx:
                validate_and_load_input(input_file)
            self.assertIn("not in participants", str(ctx.exception))

    def test_negative_amount(self):
        """Test rejection of negative amounts."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            inp = {
                "participants": ["Alice", "Bob"],
                "expenses": [
                    {
                        "payer": "Alice",
                        "amount": "-10.00",
                        "split_type": "equal",
                        "participants": ["Alice", "Bob"]
                    }
                ]
            }
            input_file = os.path.join(tmp_dir, "input.json")
            with open(input_file, 'w') as f:
                json.dump(inp, f)

            with self.assertRaises(ValueError) as ctx:
                validate_and_load_input(input_file)
            self.assertIn("positive", str(ctx.exception))

    def test_zero_amount(self):
        """Test rejection of zero amounts."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            inp = {
                "participants": ["Alice", "Bob"],
                "expenses": [
                    {
                        "payer": "Alice",
                        "amount": "0.00",
                        "split_type": "equal",
                        "participants": ["Alice", "Bob"]
                    }
                ]
            }
            input_file = os.path.join(tmp_dir, "input.json")
            with open(input_file, 'w') as f:
                json.dump(inp, f)

            with self.assertRaises(ValueError) as ctx:
                validate_and_load_input(input_file)
            self.assertIn("positive", str(ctx.exception))

    def test_invalid_json(self):
        """Test rejection of malformed JSON."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_file = os.path.join(tmp_dir, "input.json")
            with open(input_file, 'w') as f:
                f.write("{invalid json")

            with self.assertRaises(ValueError) as ctx:
                validate_and_load_input(input_file)
            self.assertIn("JSON", str(ctx.exception))

    def test_invalid_split_type(self):
        """Test rejection of unknown split_type."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            inp = {
                "participants": ["Alice", "Bob"],
                "expenses": [
                    {
                        "payer": "Alice",
                        "amount": "10.00",
                        "split_type": "unknown"
                    }
                ]
            }
            input_file = os.path.join(tmp_dir, "input.json")
            with open(input_file, 'w') as f:
                json.dump(inp, f)

            with self.assertRaises(ValueError) as ctx:
                validate_and_load_input(input_file)
            self.assertIn("unknown", str(ctx.exception))


class TestSplitTypeEqual(unittest.TestCase):
    """Test 'equal' split type."""

    def test_equal_split_two_people(self):
        """Test even split between two people."""
        allocation = allocate_expense(
            "10.00",
            "equal",
            {"participants": ["Alice", "Bob"]},
            ["Alice", "Bob"]
        )
        self.assertEqual(allocation["Alice"], 500)
        self.assertEqual(allocation["Bob"], 500)

    def test_equal_split_three_people_indivisible(self):
        """Test fair rounding when amount doesn't divide evenly."""
        allocation = allocate_expense(
            "10.00",
            "equal",
            {"participants": ["Alice", "Bob", "Charlie"]},
            ["Alice", "Bob", "Charlie"]
        )
        # 1000 cents / 3 = 333.33 each; 1 cent remainder goes to first by name (Alice)
        total = sum(allocation.values())
        self.assertEqual(total, 1000)
        self.assertEqual(allocation["Alice"], 334)  # Gets the extra cent
        self.assertEqual(allocation["Bob"], 333)
        self.assertEqual(allocation["Charlie"], 333)

    def test_equal_split_fairness(self):
        """Test that fairness rule is satisfied: no one differs from exact share by >=1 cent."""
        allocation = allocate_expense(
            "100.00",
            "equal",
            {"participants": ["A", "B", "C", "D", "E"]},
            ["A", "B", "C", "D", "E"]
        )
        for person in ["A", "B", "C", "D", "E"]:
            self.assertEqual(allocation[person], 2000)


class TestSplitTypeShares(unittest.TestCase):
    """Test 'shares' split type."""

    def test_shares_split_weighted(self):
        """Test weighted share split."""
        allocation = allocate_expense(
            "10.00",
            "shares",
            {"shares": {"Alice": 1, "Bob": 3}},
            ["Alice", "Bob"]
        )
        self.assertEqual(allocation["Alice"], 250)
        self.assertEqual(allocation["Bob"], 750)

    def test_shares_split_complex(self):
        """Test shares split with multiple participants."""
        allocation = allocate_expense(
            "100.00",
            "shares",
            {"shares": {"A": 3, "B": 2, "C": 1}},
            ["A", "B", "C"]
        )
        total = sum(allocation.values())
        self.assertEqual(total, 10000)


class TestSplitTypePercent(unittest.TestCase):
    """Test 'percent' split type."""

    def test_percent_split_simple(self):
        """Test percentage-based split."""
        allocation = allocate_expense(
            "100.00",
            "percent",
            {"percents": {"Alice": "25", "Bob": "75"}},
            ["Alice", "Bob"]
        )
        self.assertEqual(allocation["Alice"], 2500)
        self.assertEqual(allocation["Bob"], 7500)

    def test_percent_split_three_way(self):
        """Test fair rounding with percentages."""
        allocation = allocate_expense(
            "100.00",
            "percent",
            {"percents": {"A": "33.33", "B": "33.33", "C": "33.34"}},
            ["A", "B", "C"]
        )
        total = sum(allocation.values())
        self.assertEqual(total, 10000)


class TestSplitTypeExact(unittest.TestCase):
    """Test 'exact' split type."""

    def test_exact_split(self):
        """Test exact amounts split."""
        allocation = allocate_expense(
            "20.00",
            "exact",
            {"amounts": {"Alice": "7.50", "Bob": "12.50"}},
            ["Alice", "Bob"]
        )
        self.assertEqual(allocation["Alice"], 750)
        self.assertEqual(allocation["Bob"], 1250)

    def test_exact_split_validation_sum_mismatch(self):
        """Test that exact amounts must sum to expense amount."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            inp = {
                "participants": ["Alice", "Bob"],
                "expenses": [
                    {
                        "payer": "Alice",
                        "amount": "20.00",
                        "split_type": "exact",
                        "amounts": {"Alice": "7.50", "Bob": "10.00"}
                    }
                ]
            }
            input_file = os.path.join(tmp_dir, "input.json")
            with open(input_file, 'w') as f:
                json.dump(inp, f)

            with self.assertRaises(ValueError) as ctx:
                validate_and_load_input(input_file)
            self.assertIn("sum", str(ctx.exception))


class TestComputeBalances(unittest.TestCase):
    """Test balance computation."""

    def test_simple_single_expense(self):
        """Test balance calculation for a single expense."""
        participants = ["Alice", "Bob"]
        expenses = [
            {
                "payer": "Alice",
                "amount": "10.00",
                "split_type": "equal",
                "participants": ["Alice", "Bob"]
            }
        ]
        balances = compute_balances(participants, expenses)
        self.assertEqual(balances["Alice"], 500)
        self.assertEqual(balances["Bob"], -500)
        self.assertEqual(sum(balances.values()), 0)

    def test_multiple_expenses(self):
        """Test balance calculation for multiple expenses."""
        participants = ["Alice", "Bob", "Charlie"]
        expenses = [
            {
                "payer": "Alice",
                "amount": "30.00",
                "split_type": "equal",
                "participants": ["Alice", "Bob", "Charlie"]
            },
            {
                "payer": "Bob",
                "amount": "30.00",
                "split_type": "equal",
                "participants": ["Alice", "Bob", "Charlie"]
            }
        ]
        balances = compute_balances(participants, expenses)
        self.assertEqual(sum(balances.values()), 0)


class TestSettleBalances(unittest.TestCase):
    """Test settlement algorithm."""

    def test_settle_simple_two_person(self):
        """Test settlement for two people."""
        balances = {"Alice": 500, "Bob": -500}
        transfers = settle_balances(balances)
        self.assertEqual(len(transfers), 1)
        self.assertEqual(transfers[0]["from"], "Bob")
        self.assertEqual(transfers[0]["to"], "Alice")
        self.assertEqual(transfers[0]["amount_cents"], 500)

    def test_settle_multiple_debtors_creditors(self):
        """Test settlement with multiple debtors and creditors."""
        balances = {
            "A": 100,
            "B": 50,
            "C": -75,
            "D": -75
        }
        transfers = settle_balances(balances)
        self.assertLessEqual(len(transfers), 3)
        for t in transfers:
            self.assertGreater(t["amount_cents"], 0)

    def test_settle_deterministic(self):
        """Test that settlement is deterministic."""
        balances = {
            "Alice": 100,
            "Bob": 50,
            "Charlie": -75,
            "Dave": -75
        }
        transfers1 = settle_balances(balances.copy())
        transfers2 = settle_balances(balances.copy())
        s1 = json.dumps(transfers1, sort_keys=True)
        s2 = json.dumps(transfers2, sort_keys=True)
        self.assertEqual(s1, s2)


class TestMoneyConservation(unittest.TestCase):
    """Test that money is never created or destroyed."""

    def test_balances_sum_to_zero(self):
        """Test that all balances sum to zero."""
        participants = ["A", "B", "C", "D"]
        expenses = [
            {
                "payer": "A",
                "amount": "123.45",
                "split_type": "equal",
                "participants": ["A", "B", "C"]
            },
            {
                "payer": "B",
                "amount": "67.89",
                "split_type": "shares",
                "shares": {"B": 2, "C": 3, "D": 1}
            },
            {
                "payer": "C",
                "amount": "50.00",
                "split_type": "percent",
                "percents": {"A": "25", "B": "25", "C": "25", "D": "25"}
            }
        ]
        balances = compute_balances(participants, expenses)
        self.assertEqual(sum(balances.values()), 0)

    def test_allocations_sum_to_expense(self):
        """Test that each expense allocation sums to the expense amount."""
        amount_str = "123.45"
        amount_cents = int(Decimal(amount_str) * 100)

        split_configs = [
            ("equal", {"participants": ["A", "B", "C"]}, ["A", "B", "C"]),
            ("shares", {"shares": {"A": 1, "B": 2, "C": 3}}, ["A", "B", "C"]),
            ("percent", {"percents": {"A": "33.33", "B": "33.33", "C": "33.34"}}, ["A", "B", "C"]),
            ("exact", {"amounts": {"A": "40.00", "B": "41.15", "C": "42.30"}}, ["A", "B", "C"]),
        ]

        for split_type, split_data, participants in split_configs:
            allocation = allocate_expense(amount_str, split_type, split_data, participants)
            total = sum(allocation.values())
            self.assertEqual(total, amount_cents, f"Failed for {split_type}")


class TestFairnessRule(unittest.TestCase):
    """Test that no participant's share differs from exact share by >=1 cent."""

    def test_fairness_equal_split_varied_amounts(self):
        """Test fairness for equal splits with various amounts."""
        test_cases = [
            ("10.00", 2),
            ("100.00", 3),
            ("1.01", 7),
            ("999.99", 13),
        ]

        for amount_str, n_participants in test_cases:
            participants = [f"P{i}" for i in range(n_participants)]
            allocation = allocate_expense(
                amount_str,
                "equal",
                {"participants": participants},
                participants
            )
            amount_cents = int(Decimal(amount_str) * 100)
            exact_share = Decimal(amount_cents) / n_participants

            for person in participants:
                allocated = allocation[person]
                error = abs(Decimal(allocated) - exact_share)
                self.assertLess(error, 1, f"Fairness violated for {person}: error={error}")


class TestCLI(unittest.TestCase):
    """Test the command-line interface."""

    def test_cli_success(self):
        """Test successful CLI run."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            inp = {
                "participants": ["Alice", "Bob"],
                "expenses": [
                    {
                        "payer": "Alice",
                        "amount": "10.00",
                        "split_type": "equal",
                        "participants": ["Alice", "Bob"]
                    }
                ]
            }
            input_file = os.path.join(tmp_dir, "input.json")
            output_file = os.path.join(tmp_dir, "output.json")
            with open(input_file, 'w') as f:
                json.dump(inp, f)

            result = subprocess.run(
                ["python3", "splitfair.py", input_file, output_file],
                cwd=str(Path(__file__).parent.parent),
                capture_output=True,
                text=True
            )
            self.assertEqual(result.returncode, 0)
            self.assertTrue(os.path.exists(output_file))

            with open(output_file) as f:
                output = json.load(f)
            self.assertIn("balances", output)
            self.assertIn("transfers", output)

    def test_cli_invalid_input(self):
        """Test CLI rejects invalid input."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            inp = {"participants": []}
            input_file = os.path.join(tmp_dir, "input.json")
            output_file = os.path.join(tmp_dir, "output.json")
            with open(input_file, 'w') as f:
                json.dump(inp, f)

            result = subprocess.run(
                ["python3", "splitfair.py", input_file, output_file],
                cwd=str(Path(__file__).parent.parent),
                capture_output=True,
                text=True
            )
            self.assertEqual(result.returncode, 1)

    def test_cli_wrong_args(self):
        """Test CLI with wrong number of arguments."""
        result = subprocess.run(
            ["python3", "splitfair.py", "input.json"],
            cwd=str(Path(__file__).parent.parent),
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 1)


class TestDeterminism(unittest.TestCase):
    """Test that output is deterministic."""

    def test_deterministic_output_multiple_runs(self):
        """Test that running the same input produces identical output."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            inp = {
                "participants": ["Alice", "Bob", "Charlie", "Dave"],
                "expenses": [
                    {
                        "payer": "Alice",
                        "amount": "100.00",
                        "split_type": "equal",
                        "participants": ["Alice", "Bob", "Charlie"]
                    },
                    {
                        "payer": "Bob",
                        "amount": "75.50",
                        "split_type": "shares",
                        "shares": {"Bob": 1, "Charlie": 1, "Dave": 2}
                    },
                    {
                        "payer": "Charlie",
                        "amount": "200.00",
                        "split_type": "percent",
                        "percents": {"Alice": "50", "Bob": "25", "Charlie": "25"}
                    }
                ]
            }
            input_file = os.path.join(tmp_dir, "input.json")
            with open(input_file, 'w') as f:
                json.dump(inp, f)

            outputs = []
            for i in range(3):
                output_file = os.path.join(tmp_dir, f"output_{i}.json")
                result = subprocess.run(
                    ["python3", "splitfair.py", input_file, output_file],
                    cwd=str(Path(__file__).parent.parent),
                    capture_output=True,
                    text=True
                )
                self.assertEqual(result.returncode, 0)
                with open(output_file, 'rb') as f:
                    outputs.append(f.read())

            self.assertEqual(outputs[0], outputs[1])
            self.assertEqual(outputs[1], outputs[2])


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and unusual inputs."""

    def test_single_participant(self):
        """Test with a single participant."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            inp = {
                "participants": ["Alice"],
                "expenses": [
                    {
                        "payer": "Alice",
                        "amount": "100.00",
                        "split_type": "equal",
                        "participants": ["Alice"]
                    }
                ]
            }
            input_file = os.path.join(tmp_dir, "input.json")
            with open(input_file, 'w') as f:
                json.dump(inp, f)

            participants, expenses = validate_and_load_input(input_file)
            self.assertEqual(len(participants), 1)

    def test_large_amount(self):
        """Test with large amounts."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            inp = {
                "participants": ["Alice", "Bob"],
                "expenses": [
                    {
                        "payer": "Alice",
                        "amount": "999999.99",
                        "split_type": "equal",
                        "participants": ["Alice", "Bob"]
                    }
                ]
            }
            input_file = os.path.join(tmp_dir, "input.json")
            with open(input_file, 'w') as f:
                json.dump(inp, f)

            participants, expenses = validate_and_load_input(input_file)
            balances = compute_balances(participants, expenses)
            self.assertEqual(sum(balances.values()), 0)

    def test_many_participants_equal_split(self):
        """Test fairness with many participants."""
        n = 50
        participants = [f"P{i}" for i in range(n)]
        allocation = allocate_expense(
            "12345.67",
            "equal",
            {"participants": participants},
            participants
        )
        amount_cents = int(Decimal("12345.67") * 100)
        total = sum(allocation.values())
        self.assertEqual(total, amount_cents)


if __name__ == "__main__":
    unittest.main(verbosity=2)
