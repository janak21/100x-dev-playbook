#!/usr/bin/env python3
"""
splitfair — fair expense allocator and settlement calculator.

USAGE: python3 splitfair.py input.json output.json

Reads a JSON file with participants and expenses, allocates each expense fairly
(no participant's share differs from exact share by ≥1 cent), and outputs:
- balances: dict of name → int cents (positive = is owed money)
- transfers: list of minimal transfers to settle all debts
"""

import json
import sys
from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, List, Tuple


def validate_and_load_input(input_file: str) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Load and validate input JSON.

    Raises:
        ValueError: on invalid input (malformed JSON, bad schema, invalid data)
    """
    try:
        with open(input_file, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {input_file}: {e}")
    except IOError as e:
        raise ValueError(f"Cannot read {input_file}: {e}")

    # Validate top-level structure
    if not isinstance(data, dict):
        raise ValueError("Input must be a JSON object (dict)")
    if "participants" not in data:
        raise ValueError("Input missing required field: participants")
    if "expenses" not in data:
        raise ValueError("Input missing required field: expenses")

    participants = data["participants"]
    expenses = data["expenses"]

    if not isinstance(participants, list):
        raise ValueError(f"participants must be a list, got {type(participants).__name__}")
    if not isinstance(expenses, list):
        raise ValueError(f"expenses must be a list, got {type(expenses).__name__}")

    # Validate participants
    if not participants:
        raise ValueError("participants list cannot be empty")
    seen_names = set()
    for i, p in enumerate(participants):
        if not isinstance(p, str):
            raise ValueError(f"participants[{i}]: expected string, got {type(p).__name__}")
        if not p:
            raise ValueError(f"participants[{i}]: name cannot be empty")
        if p in seen_names:
            raise ValueError(f"participants[{i}]: duplicate name '{p}'")
        seen_names.add(p)

    # Validate expenses
    if not expenses:
        raise ValueError("expenses list cannot be empty")

    for i, expense in enumerate(expenses):
        _validate_expense(expense, i, seen_names)

    return participants, expenses


def _validate_expense(expense: Any, idx: int, valid_participants: set) -> None:
    """Validate a single expense object."""
    prefix = f"expenses[{idx}]"

    if not isinstance(expense, dict):
        raise ValueError(f"{prefix}: expected dict, got {type(expense).__name__}")

    # Check required fields
    required = ["payer", "amount", "split_type"]
    for field in required:
        if field not in expense:
            raise ValueError(f"{prefix}: missing required field '{field}'")

    # Validate payer
    payer = expense["payer"]
    if not isinstance(payer, str):
        raise ValueError(f"{prefix}.payer: expected string, got {type(payer).__name__}")
    if payer not in valid_participants:
        raise ValueError(f"{prefix}.payer: '{payer}' not in participants")

    # Validate amount
    amount_str = expense["amount"]
    if not isinstance(amount_str, str):
        raise ValueError(f"{prefix}.amount: expected string, got {type(amount_str).__name__}")
    try:
        amount_decimal = Decimal(amount_str)
    except Exception as e:
        raise ValueError(f"{prefix}.amount: invalid decimal '{amount_str}': {e}")
    if amount_decimal <= 0:
        raise ValueError(f"{prefix}.amount: must be positive, got {amount_decimal}")

    # Validate split_type and type-specific data
    split_type = expense["split_type"]
    if not isinstance(split_type, str):
        raise ValueError(f"{prefix}.split_type: expected string, got {type(split_type).__name__}")

    if split_type == "equal":
        if "participants" not in expense:
            raise ValueError(f"{prefix}: split_type='equal' requires 'participants' field")
        split_participants = expense["participants"]
        if not isinstance(split_participants, list):
            raise ValueError(
                f"{prefix}.participants: expected list, got {type(split_participants).__name__}"
            )
        if not split_participants:
            raise ValueError(f"{prefix}.participants: cannot be empty")
        for j, p in enumerate(split_participants):
            if not isinstance(p, str):
                raise ValueError(
                    f"{prefix}.participants[{j}]: expected string, got {type(p).__name__}"
                )
            if p not in valid_participants:
                raise ValueError(f"{prefix}.participants[{j}]: '{p}' not in participants")

    elif split_type == "shares":
        if "shares" not in expense:
            raise ValueError(f"{prefix}: split_type='shares' requires 'shares' field")
        shares = expense["shares"]
        if not isinstance(shares, dict):
            raise ValueError(f"{prefix}.shares: expected dict, got {type(shares).__name__}")
        if not shares:
            raise ValueError(f"{prefix}.shares: cannot be empty")
        total_shares = 0
        for name, weight in shares.items():
            if not isinstance(name, str):
                raise ValueError(f"{prefix}.shares: key '{name}' must be string")
            if name not in valid_participants:
                raise ValueError(f"{prefix}.shares: '{name}' not in participants")
            if not isinstance(weight, int):
                raise ValueError(
                    f"{prefix}.shares['{name}']: expected int, got {type(weight).__name__}"
                )
            if weight <= 0:
                raise ValueError(f"{prefix}.shares['{name}']: weight must be positive")
            total_shares += weight

    elif split_type == "percent":
        if "percents" not in expense:
            raise ValueError(f"{prefix}: split_type='percent' requires 'percents' field")
        percents = expense["percents"]
        if not isinstance(percents, dict):
            raise ValueError(f"{prefix}.percents: expected dict, got {type(percents).__name__}")
        if not percents:
            raise ValueError(f"{prefix}.percents: cannot be empty")
        total_percent = Decimal(0)
        for name, percent_str in percents.items():
            if not isinstance(name, str):
                raise ValueError(f"{prefix}.percents: key must be string")
            if name not in valid_participants:
                raise ValueError(f"{prefix}.percents: '{name}' not in participants")
            if not isinstance(percent_str, str):
                raise ValueError(
                    f"{prefix}.percents['{name}']: expected string, got {type(percent_str).__name__}"
                )
            try:
                percent_val = Decimal(percent_str)
            except Exception as e:
                raise ValueError(
                    f"{prefix}.percents['{name}']: invalid decimal '{percent_str}': {e}"
                )
            if percent_val < 0:
                raise ValueError(f"{prefix}.percents['{name}']: must be non-negative")
            total_percent += percent_val
        # Allow small tolerance for floating-point input rounding
        if abs(total_percent - 100) > Decimal("0.01"):
            raise ValueError(
                f"{prefix}.percents: must sum to 100, got {total_percent}"
            )

    elif split_type == "exact":
        if "amounts" not in expense:
            raise ValueError(f"{prefix}: split_type='exact' requires 'amounts' field")
        amounts = expense["amounts"]
        if not isinstance(amounts, dict):
            raise ValueError(f"{prefix}.amounts: expected dict, got {type(amounts).__name__}")
        if not amounts:
            raise ValueError(f"{prefix}.amounts: cannot be empty")
        total_amount = Decimal(0)
        for name, amount_str in amounts.items():
            if not isinstance(name, str):
                raise ValueError(f"{prefix}.amounts: key must be string")
            if name not in valid_participants:
                raise ValueError(f"{prefix}.amounts: '{name}' not in participants")
            if not isinstance(amount_str, str):
                raise ValueError(
                    f"{prefix}.amounts['{name}']: expected string, got {type(amount_str).__name__}"
                )
            try:
                amt = Decimal(amount_str)
            except Exception as e:
                raise ValueError(
                    f"{prefix}.amounts['{name}']: invalid decimal '{amount_str}': {e}"
                )
            if amt < 0:
                raise ValueError(f"{prefix}.amounts['{name}']: must be non-negative")
            total_amount += amt
        # Exact amounts must sum exactly to the expense amount
        try:
            expense_amount = Decimal(expense["amount"])
        except Exception:
            expense_amount = Decimal(0)  # Already validated above
        if total_amount != expense_amount:
            raise ValueError(
                f"{prefix}.amounts: sum {total_amount} != expense amount {expense_amount}"
            )

    else:
        raise ValueError(
            f"{prefix}.split_type: unknown type '{split_type}' "
            "(must be one of: equal, shares, percent, exact)"
        )


def allocate_expense(
    amount_str: str,
    split_type: str,
    split_data: Dict[str, Any],
    all_participants: List[str]
) -> Dict[str, int]:
    """
    Allocate an expense fairly across participants.

    Args:
        amount_str: amount as string (e.g., "12.34")
        split_type: one of "equal", "shares", "percent", "exact"
        split_data: the expense dict (includes split_type-specific fields)
        all_participants: full list of participant names

    Returns:
        Dict mapping participant name → amount in cents (int)
    """
    amount_cents = int(Decimal(amount_str) * 100)
    allocation = {p: 0 for p in all_participants}

    if split_type == "equal":
        participants = split_data["participants"]
        n = len(participants)

        # Fair rounding: compute exact share, allocate whole cents, then distribute
        # remainder to those with largest fractional parts (alphabetically for ties)
        exact_allocations = {}
        fractional_parts = {}
        total_allocated = 0

        for name in participants:
            exact_cents = Decimal(amount_cents) / n
            whole_cents = int(exact_cents)
            fractional = exact_cents - whole_cents

            exact_allocations[name] = whole_cents
            fractional_parts[name] = fractional
            total_allocated += whole_cents

        remainder = amount_cents - total_allocated

        # Allocate remainder cents to those with largest fractional parts, breaking ties alphabetically
        if remainder > 0:
            sorted_names = sorted(
                fractional_parts.keys(),
                key=lambda n: (-fractional_parts[n], n)
            )
            for i in range(remainder):
                exact_allocations[sorted_names[i]] += 1

        for name in participants:
            allocation[name] = exact_allocations[name]

    elif split_type == "shares":
        shares = split_data["shares"]
        total_shares = sum(shares.values())

        # Allocate greedily: compute exact share in cents, allocate whole cents,
        # then distribute remainder cents to those with largest fractional parts.
        exact_allocations = {}
        fractional_parts = {}
        total_allocated = 0

        for name, weight in shares.items():
            exact_cents = Decimal(amount_cents) * Decimal(weight) / Decimal(total_shares)
            whole_cents = int(exact_cents)
            fractional = exact_cents - whole_cents

            exact_allocations[name] = whole_cents
            fractional_parts[name] = fractional
            total_allocated += whole_cents

        remainder = amount_cents - total_allocated

        # Allocate remainder cents to those with largest fractional parts, breaking ties alphabetically
        if remainder > 0:
            sorted_names = sorted(
                fractional_parts.keys(),
                key=lambda n: (-fractional_parts[n], n)  # sort by fractional desc, then name asc
            )
            for i in range(remainder):
                exact_allocations[sorted_names[i]] += 1

        for name in shares:
            allocation[name] = exact_allocations[name]

    elif split_type == "percent":
        percents = split_data["percents"]

        exact_allocations = {}
        fractional_parts = {}
        total_allocated = 0

        for name, percent_str in percents.items():
            percent = Decimal(percent_str)
            exact_cents = Decimal(amount_cents) * percent / 100
            whole_cents = int(exact_cents)
            fractional = exact_cents - whole_cents

            exact_allocations[name] = whole_cents
            fractional_parts[name] = fractional
            total_allocated += whole_cents

        remainder = amount_cents - total_allocated

        if remainder > 0:
            sorted_names = sorted(
                fractional_parts.keys(),
                key=lambda n: (-fractional_parts[n], n)
            )
            for i in range(remainder):
                exact_allocations[sorted_names[i]] += 1

        for name in percents:
            allocation[name] = exact_allocations[name]

    elif split_type == "exact":
        amounts = split_data["amounts"]
        for name, amount_str_val in amounts.items():
            allocation[name] = int(Decimal(amount_str_val) * 100)

    return allocation


def compute_balances(
    participants: List[str],
    expenses: List[Dict[str, Any]]
) -> Dict[str, int]:
    """
    Compute net balance for each participant in cents.
    Positive balance = participant is owed money.
    """
    balances = {p: 0 for p in participants}

    for expense in expenses:
        payer = expense["payer"]
        amount_str = expense["amount"]
        split_type = expense["split_type"]

        amount_cents = int(Decimal(amount_str) * 100)

        # Allocate the expense
        allocation = allocate_expense(amount_str, split_type, expense, participants)

        # Update balances:
        # Payer advances money, so they become a creditor.
        balances[payer] += amount_cents

        # Each participant reduces their balance by their allocated share.
        for p, share_cents in allocation.items():
            balances[p] -= share_cents

    return balances


def settle_balances(balances: Dict[str, int]) -> List[Dict[str, Any]]:
    """
    Generate a minimal transfer plan to settle all debts.

    Uses greedy algorithm: repeatedly match the largest debtor with the largest creditor.
    Guarantees at most (n-1) transfers where n = number of participants.

    Args:
        balances: dict of name → int cents (positive = owed money)

    Returns:
        List of dicts with keys: from, to, amount_cents (all int/str)
    """
    transfers = []

    # Separate debtors and creditors
    # A participant with negative balance owes money (is a debtor)
    # A participant with positive balance is owed money (is a creditor)
    debtors = []  # (name, amount_owed_cents)
    creditors = []  # (name, amount_owed_cents)

    for name, balance in balances.items():
        if balance > 0:
            creditors.append([name, balance])
        elif balance < 0:
            debtors.append([name, -balance])

    # Sort for determinism: creditors and debtors by name
    creditors.sort(key=lambda x: x[0])
    debtors.sort(key=lambda x: x[0])

    # Greedy matching
    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        debtor_name, amount_owed = debtors[i]
        creditor_name, amount_to_receive = creditors[j]

        transfer_amount = min(amount_owed, amount_to_receive)
        transfers.append({
            "from": debtor_name,
            "to": creditor_name,
            "amount_cents": transfer_amount
        })

        debtors[i][1] -= transfer_amount
        creditors[j][1] -= transfer_amount

        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1

    # Sort transfers for determinism
    transfers.sort(key=lambda t: (t["from"], t["to"]))

    return transfers


def main() -> int:
    """Main entry point. Returns 0 on success, 1 on error."""
    if len(sys.argv) != 3:
        sys.stderr.write("USAGE: python3 splitfair.py input.json output.json\n")
        return 1

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    try:
        participants, expenses = validate_and_load_input(input_file)
        balances = compute_balances(participants, expenses)
        transfers = settle_balances(balances)

        # Prepare output
        output = {
            "balances": balances,
            "transfers": transfers
        }

        # Sort balances for determinism
        sorted_balances = {name: balances[name] for name in sorted(balances.keys())}
        output["balances"] = sorted_balances

        # Write output
        with open(output_file, 'w') as f:
            json.dump(output, f, separators=(',', ':'), sort_keys=False)

        return 0

    except (ValueError, IOError) as e:
        sys.stderr.write(f"Error: {e}\n")
        return 1
    except Exception as e:
        sys.stderr.write(f"Unexpected error: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
