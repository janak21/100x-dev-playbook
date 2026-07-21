#!/usr/bin/env python3
"""
Hostile input tests for splitfair - edge cases and adversarial scenarios.
"""

import json
import os
import sys
import tempfile
import subprocess
from decimal import Decimal


def run_splitfair(input_data: dict, tmp_dir: str) -> tuple:
    """Run splitfair, return (exit_code, output_data or None, stderr)."""
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


def test_negative_amount():
    """Negative amount should be rejected."""
    input_data = {
        "participants": ["Alice", "Bob"],
        "expenses": [
            {"payer": "Alice", "amount": "-50.00", "split_type": "equal", "participants": ["Alice", "Bob"]}
        ]
    }
    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)
    assert exit_code == 1 and output_data is None
    print("✓ test_negative_amount passed")


def test_zero_weight_share():
    """Zero weight in shares should be rejected."""
    input_data = {
        "participants": ["Alice", "Bob"],
        "expenses": [
            {"payer": "Alice", "amount": "100.00", "split_type": "shares", "shares": {"Alice": 0, "Bob": 1}}
        ]
    }
    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)
    assert exit_code == 1 and output_data is None
    print("✓ test_zero_weight_share passed")


def test_very_small_amount():
    """Very small amount (0.01) should work."""
    input_data = {
        "participants": ["Alice", "Bob"],
        "expenses": [
            {"payer": "Alice", "amount": "0.01", "split_type": "equal", "participants": ["Alice", "Bob"]}
        ]
    }
    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)
    assert exit_code == 0 and output_data is not None
    # 1 cent split: Alice pays 1, each person owes 0 (floor of 1/2=0.5)
    # Remainder: 1 cent goes to Alice (alphabetically first)
    # Alice: paid 1, owes 1, balance = 0
    # Bob: owes 0, balance = 0
    assert output_data["balances"]["Alice"] == 0
    assert output_data["balances"]["Bob"] == 0
    print("✓ test_very_small_amount passed")


def test_large_amount():
    """Large amount should work."""
    input_data = {
        "participants": ["Alice", "Bob"],
        "expenses": [
            {"payer": "Alice", "amount": "999999.99", "split_type": "equal", "participants": ["Alice", "Bob"]}
        ]
    }
    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)
    assert exit_code == 0 and output_data is not None
    print("✓ test_large_amount passed")


def test_complex_settlement():
    """Multiple participants with complex debts."""
    input_data = {
        "participants": ["A", "B", "C", "D", "E"],
        "expenses": [
            {"payer": "A", "amount": "500.00", "split_type": "equal", "participants": ["A", "B", "C", "D", "E"]},
            {"payer": "B", "amount": "300.00", "split_type": "equal", "participants": ["B", "C"]},
            {"payer": "C", "amount": "100.00", "split_type": "equal", "participants": ["C", "D", "E"]},
        ]
    }
    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)
    assert exit_code == 0
    assert output_data is not None

    # Verify all balances sum to zero
    assert sum(output_data["balances"].values()) == 0

    # Verify settlement is correct
    balances_copy = dict(output_data["balances"])
    for transfer in output_data["transfers"]:
        balances_copy[transfer["from"]] += transfer["amount_cents"]
        balances_copy[transfer["to"]] -= transfer["amount_cents"]
    for balance in balances_copy.values():
        assert balance == 0

    # Verify minimal transfers
    assert len(output_data["transfers"]) <= len(output_data["balances"]) - 1
    print("✓ test_complex_settlement passed")


def test_precision_rounding():
    """Test precision with amounts that require careful rounding."""
    input_data = {
        "participants": ["Alice", "Bob", "Chad"],
        "expenses": [
            {"payer": "Alice", "amount": "10.01", "split_type": "equal", "participants": ["Alice", "Bob", "Chad"]}
        ]
    }
    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)
    assert exit_code == 0

    # 1001 cents / 3 = 333.67, so floor is [333, 333, 333], remainder 2
    # Alphabetically: Alice, Bob, Chad -> Alice and Bob get the remainder
    # So: Alice 334, Bob 334, Chad 333
    assert output_data["balances"]["Alice"] == 1001 - 334  # 667
    assert output_data["balances"]["Bob"] == -334
    assert output_data["balances"]["Chad"] == -333
    print("✓ test_precision_rounding passed")


def test_all_one_person():
    """Expense where only one person is in the split."""
    input_data = {
        "participants": ["Alice", "Bob"],
        "expenses": [
            {"payer": "Alice", "amount": "100.00", "split_type": "exact", "amounts": {"Bob": "100.00"}}
        ]
    }
    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)
    assert exit_code == 0
    assert output_data["balances"]["Alice"] == 10000
    assert output_data["balances"]["Bob"] == -10000
    print("✓ test_all_one_person passed")


def test_settlement_with_ties():
    """Settlement where debtors/creditors have equal amounts (alphabetic tiebreak)."""
    input_data = {
        "participants": ["Zoe", "Alice", "Bob"],
        "expenses": [
            {"payer": "Zoe", "amount": "300.00", "split_type": "equal", "participants": ["Zoe", "Alice", "Bob"]}
        ]
    }
    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)
    assert exit_code == 0

    # Zoe paid 30000, owes 10000, balance = 20000
    # Alice owes 10000, balance = -10000
    # Bob owes 10000, balance = -10000

    # Settlement: match largest creditor (Zoe=20000) with largest debtor
    # Debtors: Alice=-10000, Bob=-10000 (alphabetic tiebreak -> Alice first)
    # Transfer: Alice -> Zoe 10000
    # Then: Bob -> Zoe 10000

    assert output_data["balances"]["Zoe"] == 20000
    assert output_data["balances"]["Alice"] == -10000
    assert output_data["balances"]["Bob"] == -10000

    # Verify final balances are zero
    balances_copy = dict(output_data["balances"])
    for transfer in output_data["transfers"]:
        balances_copy[transfer["from"]] += transfer["amount_cents"]
        balances_copy[transfer["to"]] -= transfer["amount_cents"]
    for balance in balances_copy.values():
        assert balance == 0

    print("✓ test_settlement_with_ties passed")


def test_missing_field():
    """Missing required fields should be rejected."""
    input_data = {
        "participants": ["Alice", "Bob"],
        "expenses": [
            {"payer": "Alice", "amount": "100.00"}  # Missing split_type
        ]
    }
    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)
    assert exit_code == 1 and output_data is None
    print("✓ test_missing_field passed")


def test_invalid_split_type():
    """Unknown split_type should be rejected."""
    input_data = {
        "participants": ["Alice", "Bob"],
        "expenses": [
            {"payer": "Alice", "amount": "100.00", "split_type": "invalid", "participants": ["Alice", "Bob"]}
        ]
    }
    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)
    assert exit_code == 1 and output_data is None
    print("✓ test_invalid_split_type passed")


def test_float_amount():
    """Float values in JSON should be handled (if they come as numbers not strings)."""
    # Create input manually to test float handling
    input_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    output_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)

    try:
        # Write JSON with float (not string)
        json.dump({
            "participants": ["Alice", "Bob"],
            "expenses": [
                {"payer": "Alice", "amount": 100.00, "split_type": "equal", "participants": ["Alice", "Bob"]}
            ]
        }, input_file)
        input_file.close()

        result = subprocess.run(
            [sys.executable, "splitfair.py", input_file.name, output_file.name],
            capture_output=True,
            text=True
        )

        # Should reject because amount must be a string
        assert result.returncode == 1
        print("✓ test_float_amount passed")
    finally:
        os.unlink(input_file.name)
        if os.path.exists(output_file.name):
            os.unlink(output_file.name)


def test_string_integer_amount():
    """String with integer value (no decimals) should work."""
    input_data = {
        "participants": ["Alice", "Bob"],
        "expenses": [
            {"payer": "Alice", "amount": "100", "split_type": "equal", "participants": ["Alice", "Bob"]}
        ]
    }
    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)
    assert exit_code == 0
    assert output_data["balances"]["Alice"] == 5000
    print("✓ test_string_integer_amount passed")


def test_trailing_zeros():
    """Amounts with trailing zeros should work."""
    input_data = {
        "participants": ["Alice", "Bob"],
        "expenses": [
            {"payer": "Alice", "amount": "100.00", "split_type": "equal", "participants": ["Alice", "Bob"]}
        ]
    }
    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)
    assert exit_code == 0
    assert output_data["balances"]["Alice"] == 5000
    print("✓ test_trailing_zeros passed")


def test_single_decimal():
    """Amount with single decimal place should work (treated as 2 decimals with 0)."""
    input_data = {
        "participants": ["Alice", "Bob"],
        "expenses": [
            {"payer": "Alice", "amount": "100.5", "split_type": "equal", "participants": ["Alice", "Bob"]}
        ]
    }
    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code, output_data, stderr = run_splitfair(input_data, tmp_dir)
    assert exit_code == 0
    # 10050 cents / 2 = 5025 each (exact division, no remainder)
    # Alice: paid 10050, owes 5025, balance = 5025
    # Bob: owes 5025, balance = -5025
    assert output_data["balances"]["Alice"] == 5025
    assert output_data["balances"]["Bob"] == -5025
    print("✓ test_single_decimal passed")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    tests = [
        test_negative_amount,
        test_zero_weight_share,
        test_very_small_amount,
        test_large_amount,
        test_complex_settlement,
        test_precision_rounding,
        test_all_one_person,
        test_settlement_with_ties,
        test_missing_field,
        test_invalid_split_type,
        test_float_amount,
        test_string_integer_amount,
        test_trailing_zeros,
        test_single_decimal,
    ]

    print("Running hostile input tests...\n")
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
