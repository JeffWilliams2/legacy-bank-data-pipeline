"""
generate_data.py
-----------------
Generates a SIMULATED legacy-bank dataset for the medallion pipeline.

The data is intentionally "messy" the way a real legacy PostgreSQL/Oracle
core-banking export would be:
  - dates in multiple inconsistent string formats
  - account types stored as cryptic legacy codes
  - transaction amounts stored as positive numbers, with a separate
    debit/credit code that implies the sign
  - blanks / nulls scattered through optional fields

No real customer data is used. All names, SSled-4s, and balances are random.

Output: four CSVs written into ../seeds/ so dbt can load them as raw sources.
"""

import csv
import os
import random
from datetime import date, timedelta

random.seed(42)  # reproducible output

HERE = os.path.dirname(os.path.abspath(__file__))
SEEDS = os.path.join(HERE, "..", "seeds")
os.makedirs(SEEDS, exist_ok=True)

N_CUSTOMERS = 800
N_ACCOUNTS = 1200
N_TRANSACTIONS = 25000
N_BRANCHES = 12

FIRST = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
         "Linda", "David", "Elizabeth", "Maria", "Jose", "Wei", "Aisha",
         "Carlos", "Fatima", "Sun", "Ravi", "Olga", "Kwame"]
LAST = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
        "Davis", "Rodriguez", "Martinez", "Chen", "Patel", "Nguyen", "Khan",
        "Okafor", "Ivanov", "Kim", "Singh", "Lopez", "Mensah"]
STATES = ["TX", "NY", "CA", "FL", "IL", "AZ", "OH", "NC", "GA", "WA"]

# Legacy account-type codes -> what they actually mean (decoded in silver)
ACCT_CODES = ["CHK", "SAV", "MMA", "CD", "LOC", "IRA"]

# Legacy transaction codes; DR=debit (money out), CR=credit (money in)
TXN_CODES = ["DR", "CR", "ATM", "ACH", "WIRE", "FEE", "INT"]
DEBIT_CODES = {"DR", "ATM", "FEE", "WIRE"}  # these reduce balance


def messy_date(d: date) -> str:
    """Return the same date in one of several legacy string formats."""
    fmt = random.choice([
        d.strftime("%Y-%m-%d"),      # 2021-03-04
        d.strftime("%m/%d/%Y"),      # 03/04/2021
        d.strftime("%d-%b-%Y"),      # 04-Mar-2021  (Oracle default-ish)
        d.strftime("%Y%m%d"),        # 20210304
    ])
    return fmt


def rand_date(start_year=2018, end_year=2025) -> date:
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


# ---- branches -------------------------------------------------------------
branches = []
for i in range(1, N_BRANCHES + 1):
    branches.append({
        "branch_id": f"BR{i:03d}",
        "branch_name": f"{random.choice(STATES)} {random.choice(['Main','Downtown','North','West','Plaza','Central'])} Branch",
        "state": random.choice(STATES),
        # FDIC cert number; a few left blank to simulate dirty source data
        "fdic_cert": "" if random.random() < 0.1 else str(random.randint(10000, 59999)),
    })

with open(os.path.join(SEEDS, "raw_branches.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["branch_id", "branch_name", "state", "fdic_cert"])
    w.writeheader()
    w.writerows(branches)

# ---- customers ------------------------------------------------------------
customers = []
for i in range(1, N_CUSTOMERS + 1):
    dob = rand_date(1945, 2004)
    customers.append({
        "customer_id": f"CUST{i:05d}",
        "full_name": f"{random.choice(FIRST)} {random.choice(LAST)}",
        "date_of_birth": messy_date(dob),
        "ssn_last4": f"{random.randint(0, 9999):04d}",
        # KYC status with some blanks (dirty data)
        "kyc_status": random.choice(["VERIFIED", "VERIFIED", "VERIFIED", "PENDING", "", "REVIEW"]),
        "risk_rating": random.choice(["LOW", "LOW", "LOW", "MEDIUM", "HIGH"]),
    })

with open(os.path.join(SEEDS, "raw_customers.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["customer_id", "full_name", "date_of_birth", "ssn_last4", "kyc_status", "risk_rating"])
    w.writeheader()
    w.writerows(customers)

# ---- accounts -------------------------------------------------------------
def fmt_balance(x: float) -> str:
    """Most balances are clean numeric strings; ~15% carry a stray $ and
    thousands-comma to simulate dirty source extracts that silver must clean."""
    if random.random() < 0.15:
        return f"${x:,.2f}"     # e.g. "$12,345.67"
    return f"{x:.2f}"           # e.g. "12345.67"


accounts = []
for i in range(1, N_ACCOUNTS + 1):
    cust = random.choice(customers)["customer_id"]
    br = random.choice(branches)["branch_id"]
    accounts.append({
        "account_id": f"ACCT{i:06d}",
        "customer_id": cust,
        "branch_id": br,
        "acct_type_code": random.choice(ACCT_CODES),
        "open_date": messy_date(rand_date()),
        "current_balance": fmt_balance(round(random.uniform(-5000, 480000), 2)),
        "status": random.choice(["OPEN", "OPEN", "OPEN", "CLOSED", "DORMANT"]),
    })

with open(os.path.join(SEEDS, "raw_accounts.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["account_id", "customer_id", "branch_id", "acct_type_code", "open_date", "current_balance", "status"])
    w.writeheader()
    w.writerows(accounts)

# ---- transactions ---------------------------------------------------------
# Seed some deliberate AML patterns so the gold layer has something to catch:
#   - large single transactions over the $10,000 CTR threshold
#   - "structuring": several same-day cash deposits just under $10,000
open_accounts = [a["account_id"] for a in accounts if a["status"] != "CLOSED"]

transactions = []
txn_counter = 1

def add_txn(account_id, txn_date, code, amount, channel):
    global txn_counter
    transactions.append({
        "txn_id": f"TXN{txn_counter:08d}",
        "account_id": account_id,
        "txn_date": messy_date(txn_date),
        "txn_code": code,
        "amount": f"{abs(amount):.2f}",  # always positive in source
        "channel": channel,
    })
    txn_counter += 1

# normal background transactions
for _ in range(N_TRANSACTIONS):
    acct = random.choice(open_accounts)
    code = random.choice(TXN_CODES)
    amt = round(random.uniform(5, 4500), 2)
    add_txn(acct, rand_date(2023, 2025), code, amt, random.choice(["ATM", "ONLINE", "BRANCH", "ACH", "WIRE"]))

# ~30 large CTR-reportable transactions (> $10,000)
for _ in range(30):
    acct = random.choice(open_accounts)
    amt = round(random.uniform(10001, 95000), 2)
    add_txn(acct, rand_date(2024, 2025), "WIRE", amt, "WIRE")

# ~15 structuring clusters: 3-4 same-day cash deposits of $9,000-$9,900
for _ in range(15):
    acct = random.choice(open_accounts)
    day = rand_date(2024, 2025)
    for _ in range(random.randint(3, 4)):
        amt = round(random.uniform(9000, 9900), 2)
        add_txn(acct, day, "CR", amt, "BRANCH")

random.shuffle(transactions)
with open(os.path.join(SEEDS, "raw_transactions.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["txn_id", "account_id", "txn_date", "txn_code", "amount", "channel"])
    w.writeheader()
    w.writerows(transactions)

print(f"Generated: {len(customers)} customers, {len(accounts)} accounts, "
      f"{len(transactions)} transactions, {len(branches)} branches")
print(f"Seeds written to: {os.path.abspath(SEEDS)}")
