#!/usr/bin/env python3
"""
Test suite for splitfair.py
Run with: python3 test_splitfair.py
"""

import json
import subprocess
import tempfile
import os
from decimal import Decimal
from pathlib import Path


class TestSplitFair:
    def __init__(self):
        self.passed = 0
        self.failed = 0

    def run_splitfair(self, input_data):
        """Helper to run splitfair and return output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = os.path.join(tmpdir, 'input.json')
            output_file = os.path.join(tmpdir, 'output.json')

            with open(input_file, 'w') as f:
                json.dump(input_data, f)

            result = subprocess.run(
                ['python3', 'splitfair.py', input_file, output_file],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return None, result.stderr

            with open(output_file, 'r') as f:
                return json.load(f), None

    def test_equal_split_simple(self):
        """Test: two people, equal split."""
        data = {
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
        output, err = self.run_splitfair(data)
        if output is None:
            print(f"FAIL test_equal_split_simple: {err}")
            self.failed += 1
            return

        # Alice paid 1000 cents, got 500 cents -> owes 500
        # Bob got 500 cents -> owed 500
        assert output['balances']['Alice'] == -500, f"Expected Alice -500, got {output['balances']['Alice']}"
        assert output['balances']['Bob'] == 500, f"Expected Bob 500, got {output['balances']['Bob']}"
        assert sum(output['balances'].values()) == 0, "Balances must sum to zero"

        # One transfer settles
        assert len(output['transfers']) == 1
        assert output['transfers'][0]['amount_cents'] == 500

        print("PASS test_equal_split_simple")
        self.passed += 1

    def test_equal_split_three_with_remainder(self):
        """Test: three people, $10 split equally -> rounding."""
        data = {
            "participants": ["A", "B", "C"],
            "expenses": [
                {
                    "payer": "A",
                    "amount": "10.00",
                    "split_type": "equal",
                    "participants": ["A", "B", "C"]
                }
            ]
        }
        output, err = self.run_splitfair(data)
        if output is None:
            print(f"FAIL test_equal_split_three: {err}")
            self.failed += 1
            return

        # 1000 cents / 3 = 333, 333, 334 (remainder 1 goes to first person)
        # A paid 1000, got 334 -> -666
        # B got 333 -> +333
        # C got 333 -> +333
        assert sum(output['balances'].values()) == 0, "Balances must sum to zero"
        
        # Verify allocations: one person gets extra cent
        allocations = sorted(output['balances'].values())
        assert allocations[0] == -666, f"Expected largest negative balance -666, got {allocations[0]}"
        assert allocations[1] == 333, f"Expected positive balance 333, got {allocations[1]}"
        assert allocations[2] == 333, f"Expected positive balance 333, got {allocations[2]}"

        print("PASS test_equal_split_three_with_remainder")
        self.passed += 1

    def test_shares_split(self):
        """Test: shares-based split."""
        data = {
            "participants": ["Alice", "Bob"],
            "expenses": [
                {
                    "payer": "Alice",
                    "amount": "100.00",
                    "split_type": "shares",
                    "shares": {"Alice": 1, "Bob": 3}
                }
            ]
        }
        output, err = self.run_splitfair(data)
        if output is None:
            print(f"FAIL test_shares_split: {err}")
            self.failed += 1
            return

        # Alice: 1/4 of 10000 = 2500, paid 10000 -> -7500
        # Bob: 3/4 of 10000 = 7500 -> +7500
        assert output['balances']['Alice'] == -7500
        assert output['balances']['Bob'] == 7500
        assert sum(output['balances'].values()) == 0

        print("PASS test_shares_split")
        self.passed += 1

    def test_percent_split(self):
        """Test: percent-based split."""
        data = {
            "participants": ["Alice", "Bob"],
            "expenses": [
                {
                    "payer": "Alice",
                    "amount": "100.00",
                    "split_type": "percent",
                    "percents": {"Alice": "50", "Bob": "50"}
                }
            ]
        }
        output, err = self.run_splitfair(data)
        if output is None:
            print(f"FAIL test_percent_split: {err}")
            self.failed += 1
            return

        assert output['balances']['Alice'] == -5000
        assert output['balances']['Bob'] == 5000
        assert sum(output['balances'].values()) == 0

        print("PASS test_percent_split")
        self.passed += 1

    def test_exact_split(self):
        """Test: exact amount split."""
        data = {
            "participants": ["Alice", "Bob", "Charlie"],
            "expenses": [
                {
                    "payer": "Alice",
                    "amount": "100.00",
                    "split_type": "exact",
                    "amounts": {"Alice": "30.00", "Bob": "40.00", "Charlie": "30.00"}
                }
            ]
        }
        output, err = self.run_splitfair(data)
        if output is None:
            print(f"FAIL test_exact_split: {err}")
            self.failed += 1
            return

        # Alice paid 10000, got 3000 -> -7000
        # Bob got 4000 -> +4000
        # Charlie got 3000 -> +3000
        assert output['balances']['Alice'] == -7000
        assert output['balances']['Bob'] == 4000
        assert output['balances']['Charlie'] == 3000
        assert sum(output['balances'].values()) == 0

        print("PASS test_exact_split")
        self.passed += 1

    def test_multiple_expenses(self):
        """Test: multiple expenses from different payers."""
        data = {
            "participants": ["Alice", "Bob"],
            "expenses": [
                {
                    "payer": "Alice",
                    "amount": "10.00",
                    "split_type": "equal",
                    "participants": ["Alice", "Bob"]
                },
                {
                    "payer": "Bob",
                    "amount": "20.00",
                    "split_type": "equal",
                    "participants": ["Alice", "Bob"]
                }
            ]
        }
        output, err = self.run_splitfair(data)
        if output is None:
            print(f"FAIL test_multiple_expenses: {err}")
            self.failed += 1
            return

        # Expense 1: Alice paid 1000, got 500 -> -500
        # Expense 2: Bob paid 2000, got 1000 -> +1000
        # Alice total: -500 + 1000 = +500
        # Bob total: +500 - 2000 = -1500
        assert output['balances']['Alice'] == 500
        assert output["balances"]["Bob"] == -500
        assert sum(output['balances'].values()) == 0

        print("PASS test_multiple_expenses")
        self.passed += 1

    def test_zero_expense(self):
        """Test: zero amount expense."""
        data = {
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
        output, err = self.run_splitfair(data)
        if output is None:
            print(f"FAIL test_zero_expense: {err}")
            self.failed += 1
            return

        assert output['balances']['Alice'] == 0
        assert output['balances']['Bob'] == 0
        assert len(output['transfers']) == 0

        print("PASS test_zero_expense")
        self.passed += 1

    def test_no_expenses(self):
        """Test: no expenses."""
        data = {
            "participants": ["Alice", "Bob"],
            "expenses": []
        }
        output, err = self.run_splitfair(data)
        if output is None:
            print(f"FAIL test_no_expenses: {err}")
            self.failed += 1
            return

        assert output['balances']['Alice'] == 0
        assert output['balances']['Bob'] == 0
        assert len(output['transfers']) == 0

        print("PASS test_no_expenses")
        self.passed += 1

    def test_settlement_simple(self):
        """Test: settlement with multiple transfers."""
        data = {
            "participants": ["Alice", "Bob", "Charlie"],
            "expenses": [
                {
                    "payer": "Alice",
                    "amount": "30.00",
                    "split_type": "equal",
                    "participants": ["Alice", "Bob", "Charlie"]
                }
            ]
        }
        output, err = self.run_splitfair(data)
        if output is None:
            print(f"FAIL test_settlement_simple: {err}")
            self.failed += 1
            return

        # 3000 cents / 3 = 1000 each
        # Alice paid 3000, got 1000 -> -2000
        # Bob, Charlie each got 1000 -> +1000 each
        # Settlement: need 2 transfers max (n-1 = 2)
        assert len(output['transfers']) <= 2
        # Verify all transfers are positive
        for t in output['transfers']:
            assert t['amount_cents'] > 0

        print("PASS test_settlement_simple")
        self.passed += 1

    def test_invalid_payer(self):
        """Test: invalid payer rejected."""
        data = {
            "participants": ["Alice", "Bob"],
            "expenses": [
                {
                    "payer": "Charlie",
                    "amount": "10.00",
                    "split_type": "equal",
                    "participants": ["Alice", "Bob"]
                }
            ]
        }
        output, err = self.run_splitfair(data)
        assert output is None, "Should reject invalid payer"
        assert "not a participant" in err
        print("PASS test_invalid_payer")
        self.passed += 1

    def test_invalid_amount(self):
        """Test: invalid amount rejected."""
        data = {
            "participants": ["Alice", "Bob"],
            "expenses": [
                {
                    "payer": "Alice",
                    "amount": "abc",
                    "split_type": "equal",
                    "participants": ["Alice", "Bob"]
                }
            ]
        }
        output, err = self.run_splitfair(data)
        assert output is None, "Should reject invalid amount"
        assert "not a valid decimal" in err
        print("PASS test_invalid_amount")
        self.passed += 1

    def test_negative_amount(self):
        """Test: negative amount rejected."""
        data = {
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
        output, err = self.run_splitfair(data)
        assert output is None, "Should reject negative amount"
        print("PASS test_negative_amount")
        self.passed += 1

    def test_exact_amount_mismatch(self):
        """Test: exact split amounts don't match."""
        data = {
            "participants": ["Alice", "Bob"],
            "expenses": [
                {
                    "payer": "Alice",
                    "amount": "100.00",
                    "split_type": "exact",
                    "amounts": {"Alice": "30.00", "Bob": "60.00"}
                }
            ]
        }
        output, err = self.run_splitfair(data)
        assert output is None, "Should reject mismatched exact amounts"
        assert "do not match" in err
        print("PASS test_exact_amount_mismatch")
        self.passed += 1

    def test_determinism(self):
        """Test: same input produces identical output."""
        data = {
            "participants": ["Charlie", "Alice", "Bob"],
            "expenses": [
                {
                    "payer": "Alice",
                    "amount": "123.45",
                    "split_type": "shares",
                    "shares": {"Alice": 2, "Bob": 3, "Charlie": 1}
                }
            ]
        }

        outputs = []
        for _ in range(3):
            output, err = self.run_splitfair(data)
            if output is None:
                print(f"FAIL test_determinism: {err}")
                self.failed += 1
                return

            with tempfile.TemporaryDirectory() as tmpdir:
                output_file = os.path.join(tmpdir, 'output.json')
                with open(output_file, 'w') as f:
                    json.dump(output, f, separators=(',', ':'), sort_keys=True)
                with open(output_file, 'r') as f:
                    json_str = f.read()
                outputs.append(json_str)

        # All outputs should be byte-identical
        assert outputs[0] == outputs[1] == outputs[2]
        print("PASS test_determinism")
        self.passed += 1

    def test_money_conservation(self):
        """Test: balances sum to zero."""
        data = {
            "participants": ["A", "B", "C", "D"],
            "expenses": [
                {"payer": "A", "amount": "50.12", "split_type": "equal", "participants": ["A", "B", "C", "D"]},
                {"payer": "B", "amount": "99.99", "split_type": "shares", "shares": {"A": 1, "B": 1, "C": 1, "D": 1}},
                {"payer": "C", "amount": "33.33", "split_type": "percent", "percents": {"A": "25", "B": "25", "C": "25", "D": "25"}},
                {"payer": "D", "amount": "0.01", "split_type": "exact", "amounts": {"A": "0.00", "B": "0.00", "C": "0.00", "D": "0.01"}},
            ]
        }
        output, err = self.run_splitfair(data)
        if output is None:
            print(f"FAIL test_money_conservation: {err}")
            self.failed += 1
            return

        total = sum(output['balances'].values())
        assert total == 0, f"Balances must sum to zero, got {total}"

        # Verify transfers settle all balances
        balances = dict(output['balances'])
        for transfer in output['transfers']:
            balances[transfer['from']] += transfer['amount_cents']
            balances[transfer['to']] -= transfer['amount_cents']

        for name, balance in balances.items():
            assert balance == 0, f"After settlement, {name} should have 0 balance, got {balance}"

        print("PASS test_money_conservation")
        self.passed += 1

    def run_all(self):
        """Run all tests."""
        print("Running splitfair tests...\n")

        self.test_equal_split_simple()
        self.test_equal_split_three_with_remainder()
        self.test_shares_split()
        self.test_percent_split()
        self.test_exact_split()
        self.test_multiple_expenses()
        self.test_zero_expense()
        self.test_no_expenses()
        self.test_settlement_simple()
        self.test_invalid_payer()
        self.test_invalid_amount()
        self.test_negative_amount()
        self.test_exact_amount_mismatch()
        self.test_determinism()
        self.test_money_conservation()

        print(f"\n{'='*50}")
        print(f"Results: {self.passed} passed, {self.failed} failed")
        print(f"{'='*50}")

        return self.failed == 0


if __name__ == "__main__":
    tester = TestSplitFair()
    success = tester.run_all()
    exit(0 if success else 1)
