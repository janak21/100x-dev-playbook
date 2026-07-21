#!/usr/bin/env python3
"""
Comprehensive tests for splitfair.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
import subprocess

def run_splitfair(input_data: dict, tmp_dir: str) -> tuple:
    """
    Run splitfair with input data, return (exit_code, output_data or None, stderr).
    """
    input_file = os.path.join(tmp_dir, "input.json")
    output_file = os.path.join(tmp_dir, "output.json")

    with open(input_file, 'w') as f:
        json.dump(input_data, f)

    result = subprocess.run(
        [sys.executable, "splitfair.py", input_file, output_file],
        capture_output=True,
        text=True
    )

    output_data = None
    if os.path.exists(output_file):
        with open(output_file, 'r') as f:
            output_data = json.load(f)

    return result.returncode, output_data, result.stderr


def test_happy_path_all_split_types():
    """Test the provided example with all 4 split types."""
    input_data = {
        "participants": ["Alice", "Bob", "Chad"],
        "expenses": [
            {"payer": "Alice", "amount": "100.00", "split_type": "equal", "participants": ["Alice", "Bob", "Chad"]},
            {"payer": "Bob",   "amount": "99.99",  "split_type": "shares",  "shares":   {"Alice": 1, "Bob": 2, "Chad": 3}},
            {"payer": "Chad",  "amount": "10.00",  "split_type": "percent", "percents": {"Alice": "33.33", "Bob": "33.33", "Chad": "33.34"}},
            {"payer": "Alice", "amount": "50.00",  "split_type": "exact",   "amounts":  {"Bob": "20.00", "Chad": "30.00"}}
        ]
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)

    assert exit_code == 0, f"Expected exit code 0, got {exit_code}. stderr: {stderr}"
    assert output_data is not None, "Expected output.json to be created"
    assert "balances" in output_data, "Output should have 'balances'"
    assert "transfers" in output_data, "Output should have 'transfers'"

    # Verify balances sum to zero
    total = sum(output_data["balances"].values())
    assert total == 0, f"Balances should sum to zero, got {total}"

    # Verify settlement brings all balances to zero
    balances_copy = dict(output_data["balances"])
    for transfer in output_data["transfers"]:
        balances_copy[transfer["from"]] += transfer["amount_cents"]
        balances_copy[transfer["to"]] -= transfer["amount_cents"]

    for name, balance in balances_copy.items():
        assert balance == 0, f"After settlement, {name} should have balance 0, got {balance}"

    print("✓ test_happy_path_all_split_types passed")


def test_equal_split_simple():
    """Test equal split with simple numbers."""
    input_data = {
        "participants": ["Alice", "Bob"],
        "expenses": [
            {"payer": "Alice", "amount": "10.00", "split_type": "equal", "participants": ["Alice", "Bob"]}
        ]
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)

    assert exit_code == 0, f"Exit code {exit_code}. stderr: {stderr}"
    assert output_data["balances"]["Alice"] == 500  # Paid 1000, owes 500
    assert output_data["balances"]["Bob"] == -500    # Owes 500

    print("✓ test_equal_split_simple passed")


def test_equal_split_with_remainder():
    """Test equal split where remainder needs to be distributed."""
    input_data = {
        "participants": ["Alice", "Bob", "Chad"],
        "expenses": [
            {"payer": "Alice", "amount": "1.00", "split_type": "equal", "participants": ["Alice", "Bob", "Chad"]}
        ]
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)

    assert exit_code == 0, f"Exit code {exit_code}. stderr: {stderr}"
    balances = output_data["balances"]

    # 100 cents / 3 = 33.33..., so should be [34, 33, 33] in alphabetical order
    # Alice paid 100 and owes 34 -> balance 66
    # Bob owes 33 -> balance -33
    # Chad owes 33 -> balance -33
    assert balances["Alice"] == 66, f"Alice balance should be 66, got {balances['Alice']}"
    assert balances["Bob"] == -33, f"Bob balance should be -33, got {balances['Bob']}"
    assert balances["Chad"] == -33, f"Chad balance should be -33, got {balances['Chad']}"

    print("✓ test_equal_split_with_remainder passed")


def test_shares_split():
    """Test shares split."""
    input_data = {
        "participants": ["Alice", "Bob", "Chad"],
        "expenses": [
            {"payer": "Alice", "amount": "100.00", "split_type": "shares", "shares": {"Alice": 1, "Bob": 2, "Chad": 3}}
        ]
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)

    assert exit_code == 0, f"Exit code {exit_code}. stderr: {stderr}"
    balances = output_data["balances"]

    # Total weight = 6
    # Alice: 10000 * 1 / 6 = 1666.67 -> 1666 (Alice pays 10000, owes 1666, balance = 8334)
    # Bob: 10000 * 2 / 6 = 3333.33 -> 3333 (owes 3333)
    # Chad: 10000 * 3 / 6 = 5000 (owes 5000)
    # Remainder: 10000 - (1666 + 3333 + 5000) = 1, give to Alice (first alphabetically)
    # So Alice owes 1667, balance = 10000 - 1667 = 8333
    assert balances["Alice"] == 8333, f"Alice balance should be 8333, got {balances['Alice']}"
    assert balances["Bob"] == -3333, f"Bob balance should be -3333, got {balances['Bob']}"
    assert balances["Chad"] == -5000, f"Chad balance should be -5000, got {balances['Chad']}"

    print("✓ test_shares_split passed")


def test_percent_split():
    """Test percent split."""
    input_data = {
        "participants": ["Alice", "Bob"],
        "expenses": [
            {"payer": "Alice", "amount": "100.00", "split_type": "percent", "percents": {"Alice": "50", "Bob": "50"}}
        ]
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)

    assert exit_code == 0, f"Exit code {exit_code}. stderr: {stderr}"
    balances = output_data["balances"]

    assert balances["Alice"] == 5000, f"Alice balance should be 5000, got {balances['Alice']}"
    assert balances["Bob"] == -5000, f"Bob balance should be -5000, got {balances['Bob']}"

    print("✓ test_percent_split passed")


def test_exact_split():
    """Test exact split."""
    input_data = {
        "participants": ["Alice", "Bob"],
        "expenses": [
            {"payer": "Alice", "amount": "100.00", "split_type": "exact", "amounts": {"Bob": "100.00"}}
        ]
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)

    assert exit_code == 0, f"Exit code {exit_code}. stderr: {stderr}"
    balances = output_data["balances"]

    assert balances["Alice"] == 10000, f"Alice balance should be 10000, got {balances['Alice']}"
    assert balances["Bob"] == -10000, f"Bob balance should be -10000, got {balances['Bob']}"

    print("✓ test_exact_split passed")


def test_payer_in_split():
    """Test that payer can appear in their own split."""
    input_data = {
        "participants": ["Alice", "Bob"],
        "expenses": [
            {"payer": "Alice", "amount": "100.00", "split_type": "equal", "participants": ["Alice", "Bob"]}
        ]
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)

    assert exit_code == 0, f"Exit code {exit_code}. stderr: {stderr}"
    # Alice paid 100, owes 50 (her share), so balance = 50
    assert output_data["balances"]["Alice"] == 5000

    print("✓ test_payer_in_split passed")


def test_error_invalid_json():
    """Test that invalid JSON is rejected."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        input_file = os.path.join(tmp_dir, "input.json")
        output_file = os.path.join(tmp_dir, "output.json")

        with open(input_file, 'w') as f:
            f.write("{invalid json")

        result = subprocess.run(
            [sys.executable, "splitfair.py", input_file, output_file],
            capture_output=True,
            text=True
        )

        assert result.returncode == 1, f"Expected exit code 1, got {result.returncode}"
        assert not os.path.exists(output_file), "Should not create output file on error"
        assert result.stderr, "Should print error to stderr"

    print("✓ test_error_invalid_json passed")


def test_error_unknown_participant():
    """Test that unknown participant names are rejected."""
    input_data = {
        "participants": ["Alice", "Bob"],
        "expenses": [
            {"payer": "Charlie", "amount": "100.00", "split_type": "equal", "participants": ["Alice", "Bob"]}
        ]
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)

    assert exit_code == 1, f"Expected exit code 1, got {exit_code}"
    assert output_data is None, "Should not create output file on error"
    assert "Unknown participant" in stderr or "Charlie" in stderr

    print("✓ test_error_unknown_participant passed")


def test_error_empty_participants():
    """Test that empty participants list is rejected."""
    input_data = {
        "participants": [],
        "expenses": []
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)

    assert exit_code == 1, f"Expected exit code 1, got {exit_code}"
    assert output_data is None, "Should not create output file on error"

    print("✓ test_error_empty_participants passed")


def test_error_duplicate_participants():
    """Test that duplicate participant names are rejected."""
    input_data = {
        "participants": ["Alice", "Bob", "Alice"],
        "expenses": []
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)

    assert exit_code == 1, f"Expected exit code 1, got {exit_code}"
    assert output_data is None, "Should not create output file on error"

    print("✓ test_error_duplicate_participants passed")


def test_error_invalid_amount_format():
    """Test that invalid amount format is rejected."""
    input_data = {
        "participants": ["Alice", "Bob"],
        "expenses": [
            {"payer": "Alice", "amount": "not_a_number", "split_type": "equal", "participants": ["Alice", "Bob"]}
        ]
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)

    assert exit_code == 1, f"Expected exit code 1, got {exit_code}"
    assert output_data is None, "Should not create output file on error"

    print("✓ test_error_invalid_amount_format passed")


def test_error_too_many_decimals():
    """Test that amounts with more than 2 decimal places are rejected."""
    input_data = {
        "participants": ["Alice", "Bob"],
        "expenses": [
            {"payer": "Alice", "amount": "100.123", "split_type": "equal", "participants": ["Alice", "Bob"]}
        ]
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)

    assert exit_code == 1, f"Expected exit code 1, got {exit_code}"
    assert output_data is None, "Should not create output file on error"

    print("✓ test_error_too_many_decimals passed")


def test_error_non_positive_amount():
    """Test that non-positive amounts are rejected."""
    input_data = {
        "participants": ["Alice", "Bob"],
        "expenses": [
            {"payer": "Alice", "amount": "0.00", "split_type": "equal", "participants": ["Alice", "Bob"]}
        ]
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)

    assert exit_code == 1, f"Expected exit code 1, got {exit_code}"
    assert output_data is None, "Should not create output file on error"

    print("✓ test_error_non_positive_amount passed")


def test_error_percent_not_100():
    """Test that percents not summing to 100 are rejected."""
    input_data = {
        "participants": ["Alice", "Bob"],
        "expenses": [
            {"payer": "Alice", "amount": "100.00", "split_type": "percent", "percents": {"Alice": "50", "Bob": "40"}}
        ]
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)

    assert exit_code == 1, f"Expected exit code 1, got {exit_code}"
    assert output_data is None, "Should not create output file on error"

    print("✓ test_error_percent_not_100 passed")


def test_error_exact_amounts_dont_sum():
    """Test that exact amounts not summing to total are rejected."""
    input_data = {
        "participants": ["Alice", "Bob"],
        "expenses": [
            {"payer": "Alice", "amount": "100.00", "split_type": "exact", "amounts": {"Bob": "50.00"}}
        ]
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)

    assert exit_code == 1, f"Expected exit code 1, got {exit_code}"
    assert output_data is None, "Should not create output file on error"

    print("✓ test_error_exact_amounts_dont_sum passed")


def test_settlement_correctness():
    """Test that settlement algorithm produces correct transfers."""
    input_data = {
        "participants": ["Alice", "Bob", "Chad"],
        "expenses": [
            {"payer": "Alice", "amount": "300.00", "split_type": "equal", "participants": ["Alice", "Bob", "Chad"]}
        ]
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)

    assert exit_code == 0, f"Exit code {exit_code}. stderr: {stderr}"

    # Verify settlement brings all balances to zero
    balances_copy = dict(output_data["balances"])
    for transfer in output_data["transfers"]:
        balances_copy[transfer["from"]] += transfer["amount_cents"]
        balances_copy[transfer["to"]] -= transfer["amount_cents"]

    for name, balance in balances_copy.items():
        assert balance == 0, f"After settlement, {name} should have balance 0, got {balance}"

    # Verify number of transfers <= n-1
    n = len(output_data["balances"])
    assert len(output_data["transfers"]) <= n - 1, f"Expected at most {n-1} transfers, got {len(output_data['transfers'])}"

    print("✓ test_settlement_correctness passed")


def test_single_participant():
    """Test with a single participant (edge case)."""
    input_data = {
        "participants": ["Alice"],
        "expenses": [
            {"payer": "Alice", "amount": "100.00", "split_type": "equal", "participants": ["Alice"]}
        ]
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)

    assert exit_code == 0, f"Exit code {exit_code}. stderr: {stderr}"
    assert output_data["balances"]["Alice"] == 0, "Single participant should have balance 0"
    assert len(output_data["transfers"]) == 0, "No transfers needed for single participant"

    print("✓ test_single_participant passed")


def test_no_expenses():
    """Test with participants but no expenses."""
    input_data = {
        "participants": ["Alice", "Bob"],
        "expenses": []
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)

    assert exit_code == 0, f"Exit code {exit_code}. stderr: {stderr}"
    assert output_data["balances"]["Alice"] == 0
    assert output_data["balances"]["Bob"] == 0
    assert len(output_data["transfers"]) == 0

    print("✓ test_no_expenses passed")


if __name__ == "__main__":
    # Change to the directory with splitfair.py
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    tests = [
        test_happy_path_all_split_types,
        test_equal_split_simple,
        test_equal_split_with_remainder,
        test_shares_split,
        test_percent_split,
        test_exact_split,
        test_payer_in_split,
        test_error_invalid_json,
        test_error_unknown_participant,
        test_error_empty_participants,
        test_error_duplicate_participants,
        test_error_invalid_amount_format,
        test_error_too_many_decimals,
        test_error_non_positive_amount,
        test_error_percent_not_100,
        test_error_exact_amounts_dont_sum,
        test_settlement_correctness,
        test_single_participant,
        test_no_expenses,
    ]

    print("Running tests...\n")
    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test_func.__name__} failed: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test_func.__name__} error: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
