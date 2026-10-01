"""Compose layer — query + row-level security + guardrails.

Each function is a pure, deterministic composition of three steps:

1. Filter the dataset by the caller's query (-> ``total_count``).
2. Apply the entitlement boundary (-> ``visible`` + ``withheld``).
3. Publish the visible rows through the guardrails; a blocking finding
   withholds the whole result and records the reason.

Nothing here calls an LLM — the tools return data, so fabrication is
structurally impossible, and the guardrails verify the output anyway.
"""

from __future__ import annotations

from typing import Any

from governed_mcp import data, guardrails
from governed_mcp.config import DATASET_VERSION
from governed_mcp.entitlements import resolve, visible_customer_ids
from governed_mcp.models import CallerClaims, QueryResult


def _finalize(
    entity: str,
    matched: int,
    visible_rows: list[dict],
    publish_rows: list[dict],
    filters: dict[str, Any],
) -> QueryResult:
    visible = len(visible_rows)
    withheld = matched - visible
    findings = guardrails.check_rows(publish_rows, entity) + guardrails.check_counts(
        matched, visible, withheld
    )
    blocking = [f for f in findings if f.severity.value == "blocking"]
    return QueryResult(
        entity=entity,
        rows=publish_rows if not blocking else [],
        total_count=matched,
        visible_count=visible,
        withheld_count=withheld,
        blocked=bool(blocking),
        blocked_reason="; ".join(f.code for f in blocking) if blocking else None,
        filters_applied=filters,
        findings=findings,
        dataset_version=DATASET_VERSION,
    )


def query_customers(
    claims: CallerClaims,
    segment: str | None = None,
    region: str | None = None,
) -> QueryResult:
    ent = resolve(claims)
    matched = [
        c
        for c in data.all_customers()
        if (segment is None or c["segment"] == segment)
        and (region is None or c["region"] == region)
    ]
    visible = [c for c in matched if ent.scope == "all" or _customer_in_scope(ent, c)]
    return _finalize(
        "customers",
        len(matched),
        visible,
        [guardrails.publish_customer(c) for c in visible],
        {"segment": segment, "region": region},
    )


def query_accounts(
    claims: CallerClaims,
    customer_id: str | None = None,
    account_type: str | None = None,
    min_balance: float | None = None,
) -> QueryResult:
    ent = resolve(claims)
    visible_ids = visible_customer_ids(ent)
    matched = [
        a
        for a in data.all_accounts()
        if (customer_id is None or a["customer_id"] == customer_id)
        and (account_type is None or a["type"] == account_type)
        and (min_balance is None or a["balance"] >= min_balance)
    ]
    visible = [a for a in matched if a["customer_id"] in visible_ids]
    return _finalize(
        "accounts",
        len(matched),
        visible,
        [guardrails.publish_account(a) for a in visible],
        {"customer_id": customer_id, "account_type": account_type, "min_balance": min_balance},
    )


def aggregate_balances(claims: CallerClaims, group_by: str = "region") -> QueryResult:
    ent = resolve(claims)
    visible_ids = visible_customer_ids(ent)
    cust_map = {c["id"]: c for c in data.all_customers()}
    visible = [a for a in data.all_accounts() if a["customer_id"] in visible_ids]

    groups: dict[str, dict[str, Any]] = {}
    for a in visible:
        if group_by == "type":
            key = a["type"]
        else:
            key = cust_map[a["customer_id"]].get(group_by, "unknown")
        g = groups.setdefault(key, {"group": key, "total_balance": 0.0, "count": 0})
        g["total_balance"] += a["balance"]
        g["count"] += 1

    rows = sorted(groups.values(), key=lambda g: -g["total_balance"])
    matched = len(data.all_accounts())
    return _finalize("aggregate", matched, visible, rows, {"group_by": group_by})


def describe_schema() -> dict[str, Any]:
    return {
        "dataset_version": DATASET_VERSION,
        "entities": {
            "customers": {"fields": sorted(guardrails.PUBLISHED_CUSTOMER_FIELDS), "restricted": sorted(guardrails.RESTRICTED_FIELDS)},
            "accounts": {"fields": sorted(guardrails.PUBLISHED_ACCOUNT_FIELDS), "masked": ["account_number"]},
        },
        "tools": ["query_customers", "query_accounts", "aggregate_balances", "describe_schema"],
        "note": "Read-only. Restricted fields are never published; account numbers are masked.",
    }


def _customer_in_scope(ent, customer: dict) -> bool:
    if ent.scope == "region":
        return customer["region"] == ent.region
    if ent.scope == "rm":
        return customer["rm_id"] == ent.rm_id
    return False
