#!/usr/bin/env python3
"""
splitfair: Fair expense splitting and settlement
USAGE: python3 splitfair.py input.json output.json
"""

import json
import sys
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict


def main():
    if len(sys.argv) != 3:
        print("USAGE: python3 splitfair.py input.json output.json", file=sys.stderr)
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    # Read input
    try:
        with open(input_file, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: input file '{input_file}' not found", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in input file: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        sys.exit(1)

    # Validate input
    try:
        validate_input(data)
    except ValueError as e:
        print(f"Invalid input: {e}", file=sys.stderr)
        sys.exit(1)

    # Process data
    try:
        output_balances, transfers = process(data)
    except Exception as e:
        print(f"Error processing input: {e}", file=sys.stderr)
        sys.exit(1)

    # Prepare output
    output = {
        "balances": output_balances,
        "transfers": transfers
    }

    # Write output
    try:
        with open(output_file, 'w') as f:
            json.dump(output, f, separators=(',', ':'), sort_keys=True)
    except Exception as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


def validate_input(data):
    """Validate input JSON structure and content."""
    if not isinstance(data, dict):
        raise ValueError("Input must be a JSON object")

    if "participants" not in data:
        raise ValueError("Missing 'participants' field")

    if "expenses" not in data:
        raise ValueError("Missing 'expenses' field")

    # Validate participants
    participants = data["participants"]
    if not isinstance(participants, list):
        raise ValueError("'participants' must be a list")

    if len(participants) == 0:
        raise ValueError("At least one participant required")

    if not all(isinstance(p, str) for p in participants):
        raise ValueError("All participants must be strings")

    if len(participants) != len(set(participants)):
        raise ValueError("Duplicate participant names")

    # Validate expenses
    expenses = data["expenses"]
    if not isinstance(expenses, list):
        raise ValueError("'expenses' must be a list")

    participant_set = set(participants)

    for i, expense in enumerate(expenses):
        validate_expense(expense, i, participant_set)


def validate_expense(expense, index, participant_set):
    """Validate a single expense."""
    if not isinstance(expense, dict):
        raise ValueError(f"Expense {index}: must be an object")

    # Validate payer
    if "payer" not in expense:
        raise ValueError(f"Expense {index}: missing 'payer'")
    payer = expense["payer"]
    if not isinstance(payer, str):
        raise ValueError(f"Expense {index}: payer must be a string")
    if payer not in participant_set:
        raise ValueError(f"Expense {index}: payer '{payer}' is not a participant")

    # Validate amount
    if "amount" not in expense:
        raise ValueError(f"Expense {index}: missing 'amount'")
    amount_str = expense["amount"]
    if not isinstance(amount_str, str):
        raise ValueError(f"Expense {index}: amount must be a string")
    try:
        amount = Decimal(amount_str)
    except:
        raise ValueError(f"Expense {index}: amount '{amount_str}' is not a valid decimal")
    if amount < 0:
        raise ValueError(f"Expense {index}: amount cannot be negative")

    # Validate split_type
    if "split_type" not in expense:
        raise ValueError(f"Expense {index}: missing 'split_type'")
    split_type = expense["split_type"]
    if not isinstance(split_type, str):
        raise ValueError(f"Expense {index}: split_type must be a string")

    # Validate split-type-specific data
    if split_type == "equal":
        validate_equal_split(expense, index, participant_set)
    elif split_type == "shares":
        validate_shares_split(expense, index, participant_set)
    elif split_type == "percent":
        validate_percent_split(expense, index, participant_set)
    elif split_type == "exact":
        validate_exact_split(expense, index, participant_set, amount)
    else:
        raise ValueError(f"Expense {index}: unknown split_type '{split_type}'")


def validate_equal_split(expense, index, participant_set):
    """Validate equal split expense."""
    if "participants" not in expense:
        raise ValueError(f"Expense {index}: equal split missing 'participants'")
    participants = expense["participants"]
    if not isinstance(participants, list):
        raise ValueError(f"Expense {index}: participants must be a list")
    if len(participants) == 0:
        raise ValueError(f"Expense {index}: must split among at least one participant")
    for p in participants:
        if not isinstance(p, str):
            raise ValueError(f"Expense {index}: participant must be a string")
        if p not in participant_set:
            raise ValueError(f"Expense {index}: participant '{p}' is not in the participant list")


def validate_shares_split(expense, index, participant_set):
    """Validate shares split expense."""
    if "shares" not in expense:
        raise ValueError(f"Expense {index}: shares split missing 'shares'")
    shares = expense["shares"]
    if not isinstance(shares, dict):
        raise ValueError(f"Expense {index}: shares must be an object")
    if len(shares) == 0:
        raise ValueError(f"Expense {index}: shares must have at least one participant")

    total_shares = Decimal(0)
    for p, share_value in shares.items():
        if not isinstance(p, str):
            raise ValueError(f"Expense {index}: share key must be a string")
        if p not in participant_set:
            raise ValueError(f"Expense {index}: share participant '{p}' is not in the participant list")
        try:
            share = Decimal(str(share_value))
        except:
            raise ValueError(f"Expense {index}: share value for '{p}' is not a valid number")
        if share < 0:
            raise ValueError(f"Expense {index}: share value cannot be negative")
        total_shares += share

    if total_shares == 0:
        raise ValueError(f"Expense {index}: total shares must be positive")


def validate_percent_split(expense, index, participant_set):
    """Validate percent split expense."""
    if "percents" not in expense:
        raise ValueError(f"Expense {index}: percent split missing 'percents'")
    percents = expense["percents"]
    if not isinstance(percents, dict):
        raise ValueError(f"Expense {index}: percents must be an object")
    if len(percents) == 0:
        raise ValueError(f"Expense {index}: percents must have at least one participant")

    total_percent = Decimal(0)
    for p, percent_value in percents.items():
        if not isinstance(p, str):
            raise ValueError(f"Expense {index}: percent key must be a string")
        if p not in participant_set:
            raise ValueError(f"Expense {index}: percent participant '{p}' is not in the participant list")
        if not isinstance(percent_value, str):
            raise ValueError(f"Expense {index}: percent value for '{p}' must be a string")
        try:
            percent = Decimal(percent_value)
        except:
            raise ValueError(f"Expense {index}: percent value for '{p}' is not a valid decimal")
        if percent < 0:
            raise ValueError(f"Expense {index}: percent value cannot be negative")
        total_percent += percent

    if total_percent == 0:
        raise ValueError(f"Expense {index}: total percents must be positive")


def validate_exact_split(expense, index, participant_set, amount):
    """Validate exact split expense."""
    if "amounts" not in expense:
        raise ValueError(f"Expense {index}: exact split missing 'amounts'")
    amounts = expense["amounts"]
    if not isinstance(amounts, dict):
        raise ValueError(f"Expense {index}: amounts must be an object")
    if len(amounts) == 0:
        raise ValueError(f"Expense {index}: amounts must have at least one participant")

    total_amount = Decimal(0)
    for p, amount_value in amounts.items():
        if not isinstance(p, str):
            raise ValueError(f"Expense {index}: amount key must be a string")
        if p not in participant_set:
            raise ValueError(f"Expense {index}: amount participant '{p}' is not in the participant list")
        if not isinstance(amount_value, str):
            raise ValueError(f"Expense {index}: amount value for '{p}' must be a string")
        try:
            amt = Decimal(amount_value)
        except:
            raise ValueError(f"Expense {index}: amount value for '{p}' is not a valid decimal")
        if amt < 0:
            raise ValueError(f"Expense {index}: amount value cannot be negative")
        total_amount += amt

    if total_amount != amount:
        raise ValueError(f"Expense {index}: exact amounts (sum={total_amount}) do not match expense amount ({amount})")


def to_cents(decimal_str):
    """Convert decimal string (e.g., '12.34') to integer cents."""
    d = Decimal(decimal_str)
    cents = (d * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return int(cents)


def process(data):
    """Process expenses and calculate balances and transfers."""
    participants = sorted(data["participants"])
    expenses = data["expenses"]

    # Calculate allocations (in cents per person per expense)
    allocations = {}  # allocations[expense_index] = {participant: cents, ...}

    for i, expense in enumerate(expenses):
        amount_cents = to_cents(expense["amount"])
        split_type = expense["split_type"]
        allocations[i] = {}

        if split_type == "equal":
            allocate_equal(allocations[i], amount_cents, expense["participants"])
        elif split_type == "shares":
            allocate_shares(allocations[i], amount_cents, expense["shares"])
        elif split_type == "percent":
            allocate_percent(allocations[i], amount_cents, expense["percents"])
        elif split_type == "exact":
            allocate_exact(allocations[i], expense["amounts"])

    # Calculate balances: money received from splits minus money paid
    balances = defaultdict(int)
    for i, expense in enumerate(expenses):
        payer = expense["payer"]
        amount_cents = to_cents(expense["amount"])

        # Payer pays the full amount
        balances[payer] -= amount_cents

        # Each participant in the split receives their share
        for participant, cents in allocations[i].items():
            balances[participant] += cents

    # Ensure all participants are in balances dict
    for p in participants:
        if p not in balances:
            balances[p] = 0

    # Calculate settlement transfers
    transfers = settle_balances(balances, participants)

    # Format output
    output_balances = {p: balances[p] for p in participants}

    return output_balances, transfers


def allocate_equal(allocation, amount_cents, split_participants):
    """Allocate expense equally among participants."""
    sorted_participants = sorted(split_participants)
    n = len(sorted_participants)
    base = amount_cents // n
    remainder = amount_cents % n

    for i, p in enumerate(sorted_participants):
        allocation[p] = base + (1 if i < remainder else 0)


def allocate_shares(allocation, amount_cents, shares):
    """Allocate expense based on shares."""
    sorted_participants = sorted(shares.keys())
    total_shares = sum(Decimal(str(shares[p])) for p in sorted_participants)

    remaining = amount_cents
    fractional_parts = []

    # First pass: allocate floor values
    for p in sorted_participants:
        share = Decimal(str(shares[p]))
        exact_cents = (Decimal(amount_cents) * share / total_shares)
        floor_cents = int(exact_cents)
        allocation[p] = floor_cents
        remaining -= floor_cents
        fractional = exact_cents - Decimal(floor_cents)
        fractional_parts.append((p, fractional))

    # Second pass: distribute remaining cents to those with highest fractional parts
    fractional_parts.sort(key=lambda x: x[1], reverse=True)
    for i in range(remaining):
        allocation[fractional_parts[i][0]] += 1


def allocate_percent(allocation, amount_cents, percents):
    """Allocate expense based on percentages."""
    sorted_participants = sorted(percents.keys())
    total_percent = sum(Decimal(percents[p]) for p in sorted_participants)

    remaining = amount_cents
    fractional_parts = []

    # First pass: allocate floor values
    for p in sorted_participants:
        percent = Decimal(percents[p])
        exact_cents = (Decimal(amount_cents) * percent / total_percent)
        floor_cents = int(exact_cents)
        allocation[p] = floor_cents
        remaining -= floor_cents
        fractional = exact_cents - Decimal(floor_cents)
        fractional_parts.append((p, fractional))

    # Second pass: distribute remaining cents
    fractional_parts.sort(key=lambda x: x[1], reverse=True)
    for i in range(remaining):
        allocation[fractional_parts[i][0]] += 1


def allocate_exact(allocation, amounts):
    """Allocate expense with exact amounts specified."""
    for p, amount_str in amounts.items():
        cents = to_cents(amount_str)
        allocation[p] = cents


def settle_balances(balances, participants):
    """
    Calculate minimal transfers to settle all balances.

    Uses a greedy algorithm:
    1. Find a creditor (positive balance) and debtor (negative balance)
    2. Transfer min(creditor, |debtor|) from debtor to creditor
    3. Remove if settled, repeat

    This uses at most n-1 transfers where n is number of participants.
    """
    transfers = []
    current_balances = dict(balances)

    while True:
        # Find a creditor (someone owed money)
        creditor = None
        for p in participants:
            if current_balances[p] > 0:
                creditor = p
                break

        if creditor is None:
            break  # All settled

        # Find a debtor (someone who owes money)
        debtor = None
        for p in participants:
            if current_balances[p] < 0:
                debtor = p
                break

        if debtor is None:
            break  # Should not happen if balances sum to zero

        # Transfer from debtor to creditor
        amount = min(current_balances[creditor], -current_balances[debtor])
        transfers.append({
            "from": debtor,
            "to": creditor,
            "amount_cents": amount
        })

        current_balances[creditor] -= amount
        current_balances[debtor] += amount

    return transfers


if __name__ == "__main__":
    main()
