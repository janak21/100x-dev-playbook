#!/usr/bin/env python3
"""
splitfair - Fair expense splitting with minimal settlement transfers.

Usage:
  python3 splitfair.py input.json output.json

Exits 0 on success (writes output.json), exits 1 on error (stderr message, no output file).
"""

import json
import sys
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from typing import Dict, List, Tuple, Any, Optional


class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


class Validator:
    """Validates input JSON structure and values."""

    @staticmethod
    def validate_amount_string(s: str) -> None:
        """Raise ValidationError if amount string is invalid."""
        if not isinstance(s, str):
            raise ValidationError(f"Amount must be a string, got {type(s).__name__}")

        try:
            d = Decimal(s)
        except (InvalidOperation, ValueError):
            raise ValidationError(f"Invalid amount format: '{s}'")

        # Check if it has more than 2 decimal places
        # Normalize to remove trailing zeros, then check the exponent
        normalized = d.normalize()
        if normalized.as_tuple().exponent < -2:
            raise ValidationError(f"Amount '{s}' has more than 2 decimal places")

        # Check if non-positive
        if d <= 0:
            raise ValidationError(f"Amount must be positive, got '{s}'")

    @staticmethod
    def validate_participants(participants: Any) -> List[str]:
        """Validate and return participants list. Raise ValidationError if invalid."""
        if not isinstance(participants, list):
            raise ValidationError("'participants' must be a list")

        if len(participants) == 0:
            raise ValidationError("'participants' list cannot be empty")

        if not all(isinstance(p, str) for p in participants):
            raise ValidationError("All participants must be strings")

        if len(participants) != len(set(participants)):
            raise ValidationError("Duplicate participant names found")

        return participants

    @staticmethod
    def validate_expense(expense: Any, all_participants: set) -> None:
        """Validate a single expense dict. Raise ValidationError if invalid."""
        if not isinstance(expense, dict):
            raise ValidationError("Each expense must be an object")

        # Check required fields
        if "payer" not in expense or "amount" not in expense or "split_type" not in expense:
            raise ValidationError("Expense must have 'payer', 'amount', and 'split_type'")

        payer = expense["payer"]
        if payer not in all_participants:
            raise ValidationError(f"Unknown participant: '{payer}'")

        # Validate amount
        Validator.validate_amount_string(expense["amount"])

        split_type = expense["split_type"]
        if split_type == "equal":
            if "participants" not in expense:
                raise ValidationError("'equal' split must have 'participants'")
            if not isinstance(expense["participants"], list):
                raise ValidationError("'participants' must be a list")
            if len(expense["participants"]) == 0:
                raise ValidationError("'participants' list cannot be empty")
            for p in expense["participants"]:
                if p not in all_participants:
                    raise ValidationError(f"Unknown participant in split: '{p}'")

        elif split_type == "shares":
            if "shares" not in expense:
                raise ValidationError("'shares' split must have 'shares'")
            if not isinstance(expense["shares"], dict):
                raise ValidationError("'shares' must be an object")
            if len(expense["shares"]) == 0:
                raise ValidationError("'shares' cannot be empty")
            for name, weight in expense["shares"].items():
                if name not in all_participants:
                    raise ValidationError(f"Unknown participant in shares: '{name}'")
                if not isinstance(weight, int) or weight <= 0:
                    raise ValidationError(f"Share weight must be positive integer, got {weight} for '{name}'")

        elif split_type == "percent":
            if "percents" not in expense:
                raise ValidationError("'percent' split must have 'percents'")
            if not isinstance(expense["percents"], dict):
                raise ValidationError("'percents' must be an object")
            if len(expense["percents"]) == 0:
                raise ValidationError("'percents' cannot be empty")

            total_percent = Decimal(0)
            for name, pct_str in expense["percents"].items():
                if name not in all_participants:
                    raise ValidationError(f"Unknown participant in percents: '{name}'")
                if not isinstance(pct_str, str):
                    raise ValidationError(f"Percent value must be string, got {type(pct_str).__name__}")
                try:
                    pct = Decimal(pct_str)
                except (InvalidOperation, ValueError):
                    raise ValidationError(f"Invalid percent value: '{pct_str}'")
                if pct < 0:
                    raise ValidationError(f"Percent cannot be negative: '{pct_str}'")
                total_percent += pct

            if total_percent != 100:
                raise ValidationError(f"Percents must sum to exactly 100, got {total_percent}")

        elif split_type == "exact":
            if "amounts" not in expense:
                raise ValidationError("'exact' split must have 'amounts'")
            if not isinstance(expense["amounts"], dict):
                raise ValidationError("'amounts' must be an object")

            total_exact = Decimal(0)
            for name, amt_str in expense["amounts"].items():
                if name not in all_participants:
                    raise ValidationError(f"Unknown participant in amounts: '{name}'")
                Validator.validate_amount_string(amt_str)
                total_exact += Decimal(amt_str)

            expense_amount = Decimal(expense["amount"])
            if total_exact != expense_amount:
                raise ValidationError(f"Exact amounts must sum to exactly {expense_amount}, got {total_exact}")

        else:
            raise ValidationError(f"Unknown split_type: '{split_type}'")


class ShareCalculator:
    """Computes share distribution for expenses."""

    @staticmethod
    def distribute_shares(
        total_cents: int,
        weights: Dict[str, int],
        all_participants: List[str]
    ) -> Dict[str, int]:
        """
        Distribute total_cents according to weights.

        Algorithm:
        1. Compute raw share = total_cents * weight / total_weight
        2. Floor each share
        3. Distribute remainder cents 1-per-person in alphabetical order

        Returns dict of name -> cents (int).
        """
        total_weight = sum(weights.values())

        # Compute floored shares
        shares = {}
        remainder = total_cents

        for name in sorted(weights.keys()):
            weight = weights[name]
            # Use integer division: (total_cents * weight) // total_weight
            share = (total_cents * weight) // total_weight
            shares[name] = share
            remainder -= share

        # Distribute remainder cents in alphabetical order
        sorted_names = sorted(shares.keys())
        for i in range(remainder):
            shares[sorted_names[i]] += 1

        return shares


class BalanceComputer:
    """Computes account balances from expenses."""

    def __init__(self, participants: List[str]):
        self.balances: Dict[str, int] = {p: 0 for p in participants}

    def add_expense(self, payer: str, amount_cents: int, shares: Dict[str, int]) -> None:
        """
        Add an expense to the balance.

        - payer pays amount_cents
        - each person in shares owes their share
        """
        self.balances[payer] += amount_cents
        for person, share_cents in shares.items():
            self.balances[person] -= share_cents

    def get_balances(self) -> Dict[str, int]:
        """Return current balances (positive = owed money, negative = owes money)."""
        return dict(self.balances)


class SettlementEngine:
    """Generates settlement transfers to bring all balances to zero."""

    @staticmethod
    def settle(balances: Dict[str, int]) -> List[Dict[str, Any]]:
        """
        Generate settlement transfers.

        Algorithm:
        - Repeatedly match the largest debtor with the largest creditor
        - Break ties alphabetically
        - Transfer min(debt, credit)
        - Repeat until all balances are zero

        Returns list of transfers: [{"from": name, "to": name, "amount_cents": int}, ...]
        """
        # Make a mutable copy
        working_balances = dict(balances)
        transfers = []

        while True:
            # Find all non-zero balances
            debtors = {name: -bal for name, bal in working_balances.items() if bal < 0}
            creditors = {name: bal for name, bal in working_balances.items() if bal > 0}

            if not debtors or not creditors:
                break

            # Find largest debtor (break ties alphabetically)
            max_debt = max(debtors.values())
            debtor = min(name for name, debt in debtors.items() if debt == max_debt)

            # Find largest creditor (break ties alphabetically)
            max_credit = max(creditors.values())
            creditor = min(name for name, credit in creditors.items() if credit == max_credit)

            # Transfer
            amount = min(debtors[debtor], creditors[creditor])
            transfers.append({
                "from": debtor,
                "to": creditor,
                "amount_cents": amount
            })
            working_balances[debtor] += amount
            working_balances[creditor] -= amount

        return transfers


def amount_to_cents(amount_str: str) -> int:
    """Convert decimal amount string to integer cents."""
    d = Decimal(amount_str)
    cents = int(d * 100)
    return cents


def process_expense(
    expense: Dict[str, Any],
    participants: List[str],
    balance_computer: BalanceComputer
) -> None:
    """
    Process a single expense: validate it, compute shares, update balances.
    """
    payer = expense["payer"]
    amount_cents = amount_to_cents(expense["amount"])
    split_type = expense["split_type"]

    if split_type == "equal":
        participant_list = expense["participants"]
        weights = {p: 1 for p in participant_list}
        shares = ShareCalculator.distribute_shares(amount_cents, weights, participants)

    elif split_type == "shares":
        weights = expense["shares"]
        shares = ShareCalculator.distribute_shares(amount_cents, weights, participants)

    elif split_type == "percent":
        weights = {name: Decimal(pct_str) for name, pct_str in expense["percents"].items()}
        # Convert percent weights to integers by treating them as thousandths (for precision)
        # Then compute shares
        total_weight = sum(Decimal(pct_str) for pct_str in expense["percents"].values())
        int_weights = {name: int(pct * 1000) for name, pct in weights.items()}
        shares = ShareCalculator.distribute_shares(amount_cents, int_weights, participants)

    elif split_type == "exact":
        shares = {name: amount_to_cents(amt_str) for name, amt_str in expense["amounts"].items()}

    balance_computer.add_expense(payer, amount_cents, shares)


def main():
    """Main entry point."""
    if len(sys.argv) != 3:
        print("Usage: python3 splitfair.py input.json output.json", file=sys.stderr)
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    try:
        # Load JSON
        with open(input_file, 'r') as f:
            data = json.load(f)

        # Validate structure
        if not isinstance(data, dict):
            raise ValidationError("Input must be a JSON object")

        if "participants" not in data or "expenses" not in data:
            raise ValidationError("Input must have 'participants' and 'expenses'")

        # Validate participants
        participants = Validator.validate_participants(data["participants"])
        all_participants_set = set(participants)

        # Validate expenses
        expenses = data["expenses"]
        if not isinstance(expenses, list):
            raise ValidationError("'expenses' must be a list")

        for i, expense in enumerate(expenses):
            try:
                Validator.validate_expense(expense, all_participants_set)
            except ValidationError as e:
                raise ValidationError(f"Error in expense {i}: {e}")

        # Compute balances
        balance_computer = BalanceComputer(participants)
        for expense in expenses:
            process_expense(expense, participants, balance_computer)

        balances = balance_computer.get_balances()

        # Compute settlement
        transfers = SettlementEngine.settle(balances)

        # Write output
        output_data = {
            "balances": balances,
            "transfers": transfers
        }

        with open(output_file, 'w') as f:
            json.dump(output_data, f)

        sys.exit(0)

    except ValidationError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
