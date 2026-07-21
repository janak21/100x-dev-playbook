#!/usr/bin/env python3
"""
splitfair: A command-line tool for fair expense splitting with settlement.

Usage: splitfair.py input.json output.json

Handles four split types:
  - equal: divide equally among participants
  - shares: weighted division by positive integer shares
  - percent: weighted division by percentages (must sum to exactly 100)
  - exact: explicit amounts per participant (must sum to expense amount)

All arithmetic is exact (integer cents) with no floating point errors.
Settlement uses a greedy algorithm matching largest debtor to largest creditor.
"""

import json
import sys
from decimal import Decimal
from collections import defaultdict


def validate_amount(amount_str):
    """
    Validate amount format and return cents as integer.

    Returns None if:
      - amount has more than 2 decimal places
      - amount is non-positive
      - amount is not a valid number
    """
    try:
        dec = Decimal(amount_str)
        # Check for at most 2 decimal places
        exponent = dec.as_tuple().exponent
        if exponent < -2:
            return None
        # Check non-positive
        if dec <= 0:
            return None
        # Convert to cents (integer)
        cents = int(dec * 100)
        return cents
    except:
        return None


def load_and_validate_input(input_file):
    """
    Load and validate input JSON file.

    Validates:
      - JSON is well-formed
      - Contains required fields: participants, expenses
      - No empty participants list
      - No duplicate participant names
      - Each expense has valid payer, amount, split_type
      - All participants referenced in expenses exist
      - Split type requirements are met (shares, percents sum, exact amounts sum, etc.)

    Raises ValueError with descriptive message on any validation failure.
    """
    try:
        with open(input_file, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        raise ValueError("Malformed JSON")
    except Exception as e:
        raise ValueError(f"Failed to read input file: {e}")

    # Validate structure
    if not isinstance(data, dict):
        raise ValueError("Input must be a JSON object")

    if 'participants' not in data or 'expenses' not in data:
        raise ValueError("Input must contain 'participants' and 'expenses'")

    participants = data['participants']
    expenses = data['expenses']

    # Validate participants list
    if not isinstance(participants, list):
        raise ValueError("participants must be a list")

    if len(participants) == 0:
        raise ValueError("participants list cannot be empty")

    if len(participants) != len(set(participants)):
        raise ValueError("Duplicate participant names")

    # Validate expenses list
    if not isinstance(expenses, list):
        raise ValueError("expenses must be a list")

    participant_set = set(participants)

    for i, expense in enumerate(expenses):
        if not isinstance(expense, dict):
            raise ValueError(f"Expense {i} is not a dict")

        # Check required fields
        if 'payer' not in expense or 'amount' not in expense or 'split_type' not in expense:
            raise ValueError(f"Expense {i} missing required fields")

        payer = expense['payer']
        amount = expense['amount']
        split_type = expense['split_type']

        # Validate payer
        if payer not in participant_set:
            raise ValueError(f"Unknown participant: {payer}")

        # Validate amount
        cents = validate_amount(amount)
        if cents is None:
            raise ValueError(f"Invalid amount in expense {i}: {amount}")

        # Validate split type and its specific requirements
        if split_type == 'equal':
            if 'participants' not in expense:
                raise ValueError(f"Expense {i} with split_type 'equal' missing 'participants'")
            split_participants = expense['participants']
            if not isinstance(split_participants, list):
                raise ValueError(f"Expense {i} participants must be a list")
            if len(split_participants) == 0:
                raise ValueError(f"Expense {i} participants list cannot be empty")
            for p in split_participants:
                if p not in participant_set:
                    raise ValueError(f"Unknown participant in expense {i}: {p}")

        elif split_type == 'shares':
            if 'shares' not in expense:
                raise ValueError(f"Expense {i} with split_type 'shares' missing 'shares'")
            shares = expense['shares']
            if not isinstance(shares, dict):
                raise ValueError(f"Expense {i} shares must be a dict")
            for p, weight in shares.items():
                if p not in participant_set:
                    raise ValueError(f"Unknown participant in expense {i}: {p}")
                if not isinstance(weight, int) or weight <= 0:
                    raise ValueError(f"Expense {i} share weight must be positive integer")

        elif split_type == 'percent':
            if 'percents' not in expense:
                raise ValueError(f"Expense {i} with split_type 'percent' missing 'percents'")
            percents = expense['percents']
            if not isinstance(percents, dict):
                raise ValueError(f"Expense {i} percents must be a dict")
            total_percent = Decimal(0)
            for p, percent_str in percents.items():
                if p not in participant_set:
                    raise ValueError(f"Unknown participant in expense {i}: {p}")
                try:
                    percent_val = Decimal(percent_str)
                    if percent_val < 0:
                        raise ValueError()
                    total_percent += percent_val
                except:
                    raise ValueError(f"Expense {i} invalid percent value: {percent_str}")
            if total_percent != 100:
                raise ValueError(f"Expense {i} percents do not sum to 100")

        elif split_type == 'exact':
            if 'amounts' not in expense:
                raise ValueError(f"Expense {i} with split_type 'exact' missing 'amounts'")
            amounts = expense['amounts']
            if not isinstance(amounts, dict):
                raise ValueError(f"Expense {i} amounts must be a dict")
            total_amount = Decimal(0)
            for p, amount_str in amounts.items():
                if p not in participant_set:
                    raise ValueError(f"Unknown participant in expense {i}: {p}")
                try:
                    amt = Decimal(amount_str)
                    # Validate amount format (at most 2 decimal places)
                    exponent = amt.as_tuple().exponent
                    if exponent < -2:
                        raise ValueError()
                    if amt < 0:
                        raise ValueError()
                    total_amount += amt
                except:
                    raise ValueError(f"Expense {i} invalid amount value: {amount_str}")
            if Decimal(amount) != total_amount:
                raise ValueError(f"Expense {i} exact amounts do not sum to expense amount")

        else:
            raise ValueError(f"Expense {i} unknown split_type: {split_type}")

    return data


def compute_splits(expense):
    """
    Compute who owes what for a single expense.

    Returns dict of {participant_name: cents_owed}

    For weighted types (shares, percent):
      1. Calculate raw_share = floor(total_cents * weight / total_weight) for each participant
      2. Calculate remainder = total_cents - sum of raw shares
      3. Distribute remainder cents one per participant in alphabetical order
    """
    payer = expense['payer']
    amount_cents = int(Decimal(expense['amount']) * 100)
    split_type = expense['split_type']

    owes = {}

    if split_type == 'equal':
        split_participants = expense['participants']
        num = len(split_participants)
        base = amount_cents // num
        remainder = amount_cents % num

        # Initialize all participants with base amount
        for p in split_participants:
            owes[p] = base

        # Distribute remaining cents to alphabetically first participants
        sorted_participants = sorted(split_participants)
        for i in range(remainder):
            owes[sorted_participants[i]] += 1

    elif split_type == 'shares':
        shares = expense['shares']
        split_participants = list(shares.keys())
        total_weight = sum(shares.values())

        # Calculate base amounts using floor division
        base_amounts = {}
        for p in split_participants:
            weight = shares[p]
            raw_share = amount_cents * weight // total_weight
            base_amounts[p] = raw_share

        # Distribute remaining cents to alphabetically first participants
        sorted_participants = sorted(split_participants)
        remaining = amount_cents - sum(base_amounts.values())
        for i in range(remaining):
            base_amounts[sorted_participants[i]] += 1

        owes = base_amounts

    elif split_type == 'percent':
        percents = expense['percents']
        split_participants = list(percents.keys())

        # Calculate base amounts using floor
        base_amounts = {}
        for p in split_participants:
            percent_val = Decimal(percents[p])
            raw_amount = Decimal(amount_cents) * percent_val / 100
            raw_share = int(raw_amount)
            base_amounts[p] = raw_share

        # Distribute remaining cents to alphabetically first participants
        sorted_participants = sorted(split_participants)
        remaining = amount_cents - sum(base_amounts.values())
        for i in range(remaining):
            base_amounts[sorted_participants[i]] += 1

        owes = base_amounts

    elif split_type == 'exact':
        amounts = expense['amounts']
        for p in amounts.keys():
            owes[p] = int(Decimal(amounts[p]) * 100)

    return owes


def compute_balances(data):
    """
    Compute balances for all participants.

    Balance = total_cents_paid - total_cents_owed
    Positive balance means person is owed money.
    Negative balance means person owes money.
    """
    participants = data['participants']
    expenses = data['expenses']

    paid = defaultdict(int)
    owed = defaultdict(int)

    for expense in expenses:
        payer = expense['payer']
        amount_cents = int(Decimal(expense['amount']) * 100)

        # Payer paid this amount
        paid[payer] += amount_cents

        # Calculate who owes what in this expense
        owes = compute_splits(expense)
        for p, cents in owes.items():
            owed[p] += cents

    # Compute final balances
    balances = {}
    for p in participants:
        balances[p] = paid[p] - owed[p]

    return balances


def compute_settlement(balances, participants):
    """
    Compute settlement transfers to bring all balances to zero.

    Algorithm (as specified in requirements):
      1. Repeatedly match largest debtor with largest creditor
      2. Break ties alphabetically
      3. Transfer min(debt, credit)
      4. Update balances
      5. Repeat until all balanced

    Guarantees: uses at most (n-1) transfers where n = number of participants
    """
    transfers = []

    # Make a mutable copy of balances
    balances_copy = dict(balances)

    while True:
        # Find largest debtor (most negative balance)
        debtors = [(name, -bal) for name, bal in balances_copy.items() if bal < 0]
        if not debtors:
            break
        debtors.sort(key=lambda x: (-x[1], x[0]))  # Sort by amount (desc), then name (asc)
        debtor_name, debt = debtors[0]

        # Find largest creditor (most positive balance)
        creditors = [(name, bal) for name, bal in balances_copy.items() if bal > 0]
        if not creditors:
            break
        creditors.sort(key=lambda x: (-x[1], x[0]))  # Sort by amount (desc), then name (asc)
        creditor_name, credit = creditors[0]

        # Transfer minimum of debt and credit
        transfer_amount = min(debt, credit)
        transfers.append({
            "from": debtor_name,
            "to": creditor_name,
            "amount_cents": transfer_amount
        })

        # Update balances after transfer
        balances_copy[debtor_name] += transfer_amount
        balances_copy[creditor_name] -= transfer_amount

    return transfers


def main():
    """Main entry point."""
    if len(sys.argv) != 3:
        print("Usage: splitfair.py input.json output.json", file=sys.stderr)
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    # Validate and load input
    try:
        data = load_and_validate_input(input_file)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Compute balances and settlement
    try:
        balances = compute_balances(data)
        transfers = compute_settlement(balances, data['participants'])

        output = {
            "balances": balances,
            "transfers": transfers
        }

        # Write output
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
