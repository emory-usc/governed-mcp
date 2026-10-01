"""Deterministic synthetic dataset.

Fully synthetic customers + accounts, generated from fixed constants (no
randomness at import time), so every run and every test sees the same book.
Nothing here is real customer data.

Layout: 6 regions x 6 customers = 36 customers, each with 1-3 accounts
(~72 accounts). Every customer belongs to exactly one relationship manager
(one RM per region) and carries a restricted ``tax_id`` that is never published.
"""

from __future__ import annotations

from typing import Any

REGIONS = ["north", "south", "east", "west", "central", "midwest"]
SEGMENTS = ["retail", "smb", "commercial"]
ACCOUNT_TYPES = ["checking", "savings", "loan"]
RMS = [f"rm-{i:02d}" for i in range(1, 7)]  # one RM per region


def _generate() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    customers: list[dict[str, Any]] = []
    accounts: list[dict[str, Any]] = []
    cust_seq = 1
    acct_seq = 100001
    for region_idx, region in enumerate(REGIONS):
        rm = RMS[region_idx]
        for i in range(6):
            cust_id = f"cust-{cust_seq:03d}"
            segment = SEGMENTS[cust_seq % 3]
            tax_id = f"TAX-{700000000 + cust_seq}"  # restricted — never published
            customers.append(
                {
                    "id": cust_id,
                    "name": f"{region.title()} Customer {cust_seq:02d}",
                    "segment": segment,
                    "region": region,
                    "rm_id": rm,
                    "tax_id": tax_id,
                }
            )
            n_accounts = 1 + (cust_seq % 3)
            for a in range(n_accounts):
                acct_type = ACCOUNT_TYPES[(cust_seq + a) % 3]
                balance = float(1000 * ((cust_seq * 7) % 97 + 1) + a * 500)
                accounts.append(
                    {
                        "id": f"acct-{acct_seq}",
                        "customer_id": cust_id,
                        "type": acct_type,
                        "balance": balance,
                        "currency": "USD",
                        "account_number": f"ACCT-{acct_seq}",
                    }
                )
                acct_seq += 1
            cust_seq += 1
    return customers, accounts


_CUSTOMERS, _ACCOUNTS = _generate()


def all_customers() -> list[dict[str, Any]]:
    return [dict(c) for c in _CUSTOMERS]


def all_accounts() -> list[dict[str, Any]]:
    return [dict(a) for a in _ACCOUNTS]
