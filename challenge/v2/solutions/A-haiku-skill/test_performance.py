#!/usr/bin/env python3
"""
Performance test: 50 participants, 5000 expenses, must run in <10 seconds.
"""

import json
import time
import tempfile
import subprocess
from pathlib import Path


def generate_large_input(n_participants=50, n_expenses=5000):
    """Generate a large test input."""
    participants = [f"P{i}" for i in range(n_participants)]

    expenses = []
    for i in range(n_expenses):
        if i % 4 == 0:
            # Equal split
            split_count = min(5, n_participants)
            expenses.append({
                "payer": participants[i % n_participants],
                "amount": f"{10.00 + (i % 100) * 0.01:.2f}",
                "split_type": "equal",
                "participants": participants[:split_count]
            })
        elif i % 4 == 1:
            # Shares split
            shares = {participants[j]: j + 1 for j in range(min(3, n_participants))}
            expenses.append({
                "payer": participants[i % n_participants],
                "amount": f"{50.00 + (i % 100) * 0.01:.2f}",
                "split_type": "shares",
                "shares": shares
            })
        elif i % 4 == 2:
            # Percent split
            percents = {
                participants[0]: "50",
                participants[1]: "30",
                participants[2]: "20"
            }
            expenses.append({
                "payer": participants[i % n_participants],
                "amount": f"{25.00 + (i % 100) * 0.01:.2f}",
                "split_type": "percent",
                "percents": percents
            })
        else:
            # Exact split
            amounts = {
                participants[0]: f"{10.00 + (i % 10) * 0.1:.2f}",
                participants[1]: f"{15.00 + (i % 10) * 0.1:.2f}"
            }
            expenses.append({
                "payer": participants[i % n_participants],
                "amount": f"{25.00 + (i % 10) * 0.2:.2f}",
                "split_type": "exact",
                "amounts": amounts
            })

    return {
        "participants": participants,
        "expenses": expenses
    }


if __name__ == "__main__":
    print("Generating large input: 50 participants, 5000 expenses...")
    input_data = generate_large_input(50, 5000)

    with tempfile.TemporaryDirectory() as tmp_dir:
        input_file = Path(tmp_dir) / "input.json"
        output_file = Path(tmp_dir) / "output.json"

        with open(input_file, 'w') as f:
            json.dump(input_data, f)

        print(f"Input file size: {input_file.stat().st_size / 1024:.1f} KB")
        print(f"Running splitfair.py...")

        start = time.time()
        result = subprocess.run(
            ["python3", "splitfair.py", str(input_file), str(output_file)],
            capture_output=True,
            text=True
        )
        elapsed = time.time() - start

        if result.returncode != 0:
            print(f"ERROR: {result.stderr}")
            exit(1)

        print(f"Completed in {elapsed:.2f} seconds")

        if elapsed > 10:
            print(f"FAILED: Exceeded 10-second limit ({elapsed:.2f}s > 10s)")
            exit(1)
        else:
            print(f"PASSED: Under 10-second limit ({elapsed:.2f}s < 10s)")

        with open(output_file) as f:
            output = json.load(f)

        print(f"Output file size: {output_file.stat().st_size / 1024:.1f} KB")
        print(f"Participants in balances: {len(output['balances'])}")
        print(f"Number of transfers: {len(output['transfers'])}")
        print(f"Max transfers allowed: {len(input_data['participants']) - 1}")

        if len(output['transfers']) > len(input_data['participants']) - 1:
            print(f"FAILED: Too many transfers ({len(output['transfers'])} > {len(input_data['participants']) - 1})")
            exit(1)

        # Verify money conservation
        total_balance = sum(output['balances'].values())
        if total_balance != 0:
            print(f"FAILED: Balances don't sum to zero (sum={total_balance})")
            exit(1)

        print("All performance tests PASSED!")
