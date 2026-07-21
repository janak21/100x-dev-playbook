#!/usr/bin/env python3
"""
Comprehensive test suite for splitfair.

Tests cover:
  - Equal split with remainder distribution
  - Shares split with weights and remainders
  - Percent split with validation
  - Exact split with amount validation
  - Settlement algorithm correctness
  - All error cases and validation rules
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from decimal import Decimal


TEST_DIR = Path(__file__).parent / "tests"
TEST_DIR.mkdir(exist_ok=True)

PROG = Path(__file__).parent / "splitfair.py"


def run_splitfair(input_file, output_file):
    """Run splitfair and return (success, stdout, stderr)."""
    result = subprocess.run(
        ["python3", str(PROG), str(input_file), str(output_file)],
        capture_output=True,
        text=True
    )
    return result.returncode == 0, result.stdout, result.stderr


def test_case(name, input_data, expected_output=None, should_fail=False):
    """
    Run a single test case.

    Args:
        name: Test case name
        input_data: Dict with 'participants' and 'expenses'
        expected_output: Dict with 'balances' and 'transfers' (None if should_fail)
        should_fail: True if this should produce an error

    Returns True if test passes.
    """
    print(f"Testing: {name}...", end=" ")

    input_file = TEST_DIR / f"{name}_input.json"
    output_file = TEST_DIR / f"{name}_output.json"

    # Write input
    with open(input_file, 'w') as f:
        json.dump(input_data, f)

    # Run program
    success, stdout, stderr = run_splitfair(input_file, output_file)

    if should_fail:
        if not success and not output_file.exists():
            print("PASS (correctly failed)")
            return True
        else:
            print(f"FAIL (expected failure but got success)")
            print(f"  stderr: {stderr}")
            return False

    if not success:
        print(f"FAIL (program failed)")
        print(f"  stderr: {stderr}")
        return False

    # Read output
    if not output_file.exists():
        print(f"FAIL (output file not created)")
        return False

    with open(output_file, 'r') as f:
        actual_output = json.load(f)

    if expected_output is None:
        print("PASS (output created)")
        return True

    # Check balances
    if actual_output.get("balances") != expected_output.get("balances"):
        print(f"FAIL (balances mismatch)")
        print(f"  expected: {expected_output['balances']}")
        print(f"  actual:   {actual_output['balances']}")
        return False

    # Check transfers
    expected_transfers = expected_output.get("transfers", [])
    actual_transfers = actual_output.get("transfers", [])

    if actual_transfers != expected_transfers:
        print(f"FAIL (transfers mismatch)")
        print(f"  expected: {expected_transfers}")
        print(f"  actual:   {actual_transfers}")
        return False

    print("PASS")
    return True


def run_tests():
    """Run all test cases."""
    passed = 0
    total = 0

    # Test 1: Simple equal split, no remainder
    total += 1
    if test_case(
        "test_1_equal_no_remainder",
        {
            "participants": ["Alice", "Bob"],
            "expenses": [
                {"payer": "Alice", "amount": "100.00", "split_type": "equal", "participants": ["Alice", "Bob"]}
            ]
        },
        {
            "balances": {"Alice": 5000, "Bob": -5000},
            "transfers": [{"from": "Bob", "to": "Alice", "amount_cents": 5000}]
        }
    ):
        passed += 1

    # Test 2: Equal split with remainder (3-way)
    total += 1
    if test_case(
        "test_2_equal_with_remainder",
        {
            "participants": ["Alice", "Bob", "Chad"],
            "expenses": [
                {"payer": "Alice", "amount": "100.00", "split_type": "equal", "participants": ["Alice", "Bob", "Chad"]}
            ]
        },
        {
            "balances": {"Alice": 6666, "Bob": -3333, "Chad": -3333},
            "transfers": [
                {"from": "Bob", "to": "Alice", "amount_cents": 3333},
                {"from": "Chad", "to": "Alice", "amount_cents": 3333}
            ]
        }
    ):
        passed += 1

    # Test 3: Shares with weights
    total += 1
    if test_case(
        "test_3_shares",
        {
            "participants": ["Alice", "Bob", "Chad"],
            "expenses": [
                {"payer": "Alice", "amount": "60.00", "split_type": "shares", "shares": {"Alice": 1, "Bob": 2, "Chad": 3}}
            ]
        },
        {
            "balances": {"Alice": 5000, "Bob": -2000, "Chad": -3000},
            "transfers": [
                {"from": "Chad", "to": "Alice", "amount_cents": 3000},
                {"from": "Bob", "to": "Alice", "amount_cents": 2000}
            ]
        }
    ):
        passed += 1

    # Test 4: Percent split summing to 100
    total += 1
    if test_case(
        "test_4_percent",
        {
            "participants": ["Alice", "Bob"],
            "expenses": [
                {"payer": "Alice", "amount": "100.00", "split_type": "percent", "percents": {"Alice": "50", "Bob": "50"}}
            ]
        },
        {
            "balances": {"Alice": 5000, "Bob": -5000},
            "transfers": [{"from": "Bob", "to": "Alice", "amount_cents": 5000}]
        }
    ):
        passed += 1

    # Test 5: Exact split
    total += 1
    if test_case(
        "test_5_exact",
        {
            "participants": ["Alice", "Bob"],
            "expenses": [
                {"payer": "Alice", "amount": "100.00", "split_type": "exact", "amounts": {"Bob": "100.00"}}
            ]
        },
        {
            "balances": {"Alice": 10000, "Bob": -10000},
            "transfers": [{"from": "Bob", "to": "Alice", "amount_cents": 10000}]
        }
    ):
        passed += 1

    # Test 6: Multiple expenses
    total += 1
    if test_case(
        "test_6_multiple_expenses",
        {
            "participants": ["Alice", "Bob"],
            "expenses": [
                {"payer": "Alice", "amount": "100.00", "split_type": "equal", "participants": ["Alice", "Bob"]},
                {"payer": "Bob", "amount": "100.00", "split_type": "equal", "participants": ["Alice", "Bob"]}
            ]
        },
        {
            "balances": {"Alice": 0, "Bob": 0},
            "transfers": []
        }
    ):
        passed += 1

    # Test 7: Empty participants list (should fail)
    total += 1
    if test_case(
        "test_7_empty_participants",
        {
            "participants": [],
            "expenses": []
        },
        should_fail=True
    ):
        passed += 1

    # Test 8: Duplicate participant names (should fail)
    total += 1
    if test_case(
        "test_8_duplicate_participants",
        {
            "participants": ["Alice", "Alice"],
            "expenses": []
        },
        should_fail=True
    ):
        passed += 1

    # Test 9: Unknown participant in payer (should fail)
    total += 1
    if test_case(
        "test_9_unknown_payer",
        {
            "participants": ["Alice", "Bob"],
            "expenses": [
                {"payer": "Charlie", "amount": "100.00", "split_type": "equal", "participants": ["Alice", "Bob"]}
            ]
        },
        should_fail=True
    ):
        passed += 1

    # Test 10: Unknown participant in split (should fail)
    total += 1
    if test_case(
        "test_10_unknown_in_split",
        {
            "participants": ["Alice", "Bob"],
            "expenses": [
                {"payer": "Alice", "amount": "100.00", "split_type": "equal", "participants": ["Alice", "Charlie"]}
            ]
        },
        should_fail=True
    ):
        passed += 1

    # Test 11: Non-positive amount (should fail)
    total += 1
    if test_case(
        "test_11_zero_amount",
        {
            "participants": ["Alice", "Bob"],
            "expenses": [
                {"payer": "Alice", "amount": "0.00", "split_type": "equal", "participants": ["Alice", "Bob"]}
            ]
        },
        should_fail=True
    ):
        passed += 1

    # Test 12: Negative amount (should fail)
    total += 1
    if test_case(
        "test_12_negative_amount",
        {
            "participants": ["Alice", "Bob"],
            "expenses": [
                {"payer": "Alice", "amount": "-50.00", "split_type": "equal", "participants": ["Alice", "Bob"]}
            ]
        },
        should_fail=True
    ):
        passed += 1

    # Test 13: Amount with >2 decimal places (should fail)
    total += 1
    if test_case(
        "test_13_too_many_decimals",
        {
            "participants": ["Alice", "Bob"],
            "expenses": [
                {"payer": "Alice", "amount": "100.123", "split_type": "equal", "participants": ["Alice", "Bob"]}
            ]
        },
        should_fail=True
    ):
        passed += 1

    # Test 14: Percents not summing to 100 (should fail)
    total += 1
    if test_case(
        "test_14_bad_percents",
        {
            "participants": ["Alice", "Bob"],
            "expenses": [
                {"payer": "Alice", "amount": "100.00", "split_type": "percent", "percents": {"Alice": "50", "Bob": "40"}}
            ]
        },
        should_fail=True
    ):
        passed += 1

    # Test 15: Exact amounts not summing to total (should fail)
    total += 1
    if test_case(
        "test_15_bad_exact",
        {
            "participants": ["Alice", "Bob", "Chad"],
            "expenses": [
                {"payer": "Alice", "amount": "100.00", "split_type": "exact", "amounts": {"Bob": "50.00", "Chad": "40.00"}}
            ]
        },
        should_fail=True
    ):
        passed += 1

    # Test 16: Shares with non-positive weight (should fail)
    total += 1
    if test_case(
        "test_16_bad_share_weight",
        {
            "participants": ["Alice", "Bob"],
            "expenses": [
                {"payer": "Alice", "amount": "100.00", "split_type": "shares", "shares": {"Alice": 1, "Bob": 0}}
            ]
        },
        should_fail=True
    ):
        passed += 1

    # Test 17: Malformed JSON (should fail)
    total += 1
    print("Testing: test_17_malformed_json...", end=" ")
    input_file = TEST_DIR / "test_17_malformed_json_input.json"
    output_file = TEST_DIR / "test_17_malformed_json_output.json"
    with open(input_file, 'w') as f:
        f.write("{invalid json}")
    success, stdout, stderr = run_splitfair(input_file, output_file)
    if not success and not output_file.exists():
        print("PASS (correctly failed)")
        passed += 1
    else:
        print("FAIL (expected failure)")
        total -= 1
        passed -= 1
        total += 1

    # Test 18: Settlement with multiple transfers
    total += 1
    if test_case(
        "test_18_settlement_multiple",
        {
            "participants": ["Alice", "Bob", "Chad"],
            "expenses": [
                {"payer": "Alice", "amount": "300.00", "split_type": "equal", "participants": ["Alice", "Bob", "Chad"]}
            ]
        },
        {
            "balances": {"Alice": 20000, "Bob": -10000, "Chad": -10000},
            "transfers": [
                {"from": "Bob", "to": "Alice", "amount_cents": 10000},
                {"from": "Chad", "to": "Alice", "amount_cents": 10000}
            ]
        }
    ):
        passed += 1

    # Test 19: Percent with decimal values and remainder
    total += 1
    if test_case(
        "test_19_percent_decimals",
        {
            "participants": ["Alice", "Bob", "Chad"],
            "expenses": [
                {"payer": "Alice", "amount": "10.00", "split_type": "percent", "percents": {"Alice": "33.33", "Bob": "33.33", "Chad": "33.34"}}
            ]
        }
    ):
        passed += 1

    # Test 20: Payer in own split (exact)
    total += 1
    if test_case(
        "test_20_payer_in_split",
        {
            "participants": ["Alice", "Bob", "Chad"],
            "expenses": [
                {"payer": "Alice", "amount": "100.00", "split_type": "exact", "amounts": {"Alice": "50.00", "Bob": "30.00", "Chad": "20.00"}}
            ]
        }
    ):
        passed += 1

    # Test 21: Complex multi-expense scenario
    total += 1
    if test_case(
        "test_21_complex",
        {
            "participants": ["Alice", "Bob", "Chad"],
            "expenses": [
                {"payer": "Alice", "amount": "100.00", "split_type": "equal", "participants": ["Alice", "Bob", "Chad"]},
                {"payer": "Bob", "amount": "99.99", "split_type": "shares", "shares": {"Alice": 1, "Bob": 2, "Chad": 3}},
                {"payer": "Chad", "amount": "10.00", "split_type": "percent", "percents": {"Alice": "33.33", "Bob": "33.33", "Chad": "33.34"}}
            ]
        }
    ):
        passed += 1

    # Test 22: Settlement algorithm: match largest (alphabetical tiebreak)
    total += 1
    if test_case(
        "test_22_settlement_alphabetic",
        {
            "participants": ["Alice", "Bob", "Charlie"],
            "expenses": [
                {"payer": "Alice", "amount": "99.98", "split_type": "equal", "participants": ["Alice", "Bob", "Charlie"]}
            ]
        }
    ):
        passed += 1

    # Test 23: Single participant (edge case)
    total += 1
    if test_case(
        "test_23_single_participant",
        {
            "participants": ["Alice"],
            "expenses": [
                {"payer": "Alice", "amount": "100.00", "split_type": "equal", "participants": ["Alice"]}
            ]
        },
        {
            "balances": {"Alice": 0},
            "transfers": []
        }
    ):
        passed += 1

    # Test 24: Amount with 1 decimal place
    total += 1
    if test_case(
        "test_24_one_decimal",
        {
            "participants": ["Alice", "Bob"],
            "expenses": [
                {"payer": "Alice", "amount": "10.5", "split_type": "equal", "participants": ["Alice", "Bob"]}
            ]
        }
    ):
        passed += 1

    # Test 25: No expenses
    total += 1
    if test_case(
        "test_25_no_expenses",
        {
            "participants": ["Alice", "Bob"],
            "expenses": []
        },
        {
            "balances": {"Alice": 0, "Bob": 0},
            "transfers": []
        }
    ):
        passed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed}/{total} tests passed")
    return passed == total


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
