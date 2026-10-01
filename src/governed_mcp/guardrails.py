"""Deterministic guardrails — the second, independent boundary.

Even after row-level filtering, a deterministic policy layer runs in code and
can withhold a result. It checks three things:

1. The published field surface — a restricted field (``tax_id``) or any field
   outside the allow-list is a blocking finding.
2. PII masking — a raw account number in a published result is a blocking
   finding.
3. Count integrity — ``visible + withheld == total`` must hold, so a row can
   never be silently dropped; it is either visible or counted as withheld.

The guardrails run on every result, independent of the data boundary, so the
two layers fail differently.
"""

from __future__ import annotations

from governed_mcp.models import Finding, Severity

PUBLISHED_CUSTOMER_FIELDS = {"id", "name", "segment", "region", "rm_id"}
PUBLISHED_ACCOUNT_FIELDS = {"id", "customer_id", "type", "balance", "currency", "account_number"}
PUBLISHED_AGGREGATE_FIELDS = {"group", "total_balance", "count"}

RESTRICTED_FIELDS = {"tax_id"}

_ALLOWLISTS = {
    "customers": PUBLISHED_CUSTOMER_FIELDS,
    "accounts": PUBLISHED_ACCOUNT_FIELDS,
    "aggregate": PUBLISHED_AGGREGATE_FIELDS,
}


def mask_account_number(num: str) -> str:
    return ("****-" + num[-4:]) if len(num) > 4 else "****"


def publish_customer(c: dict) -> dict:
    return {k: c[k] for k in PUBLISHED_CUSTOMER_FIELDS if k in c}


def publish_account(a: dict) -> dict:
    out = {k: a[k] for k in PUBLISHED_ACCOUNT_FIELDS if k in a}
    if "account_number" in out:
        out["account_number"] = mask_account_number(out["account_number"])
    return out


def check_rows(rows: list[dict], entity: str) -> list[Finding]:
    allowlist = _ALLOWLISTS[entity]
    findings: list[Finding] = []
    for i, row in enumerate(rows):
        for key in row:
            if key in RESTRICTED_FIELDS:
                findings.append(
                    Finding(
                        code="restricted_field_leak",
                        severity=Severity.BLOCKING,
                        message=f"row {i}: restricted field {key!r} present",
                    )
                )
            if key not in allowlist:
                findings.append(
                    Finding(
                        code="unpublished_field",
                        severity=Severity.BLOCKING,
                        message=f"row {i}: field {key!r} not in published surface",
                    )
                )
        if entity == "accounts" and "account_number" in row and row["account_number"].startswith("ACCT-"):
            findings.append(
                Finding(
                    code="unmasked_account_number",
                    severity=Severity.BLOCKING,
                    message=f"row {i}: raw account number leaked",
                )
            )
    return findings


def check_counts(total: int, visible: int, withheld: int) -> list[Finding]:
    if visible + withheld != total:
        return [
            Finding(
                code="count_mismatch",
                severity=Severity.BLOCKING,
                message=f"visible({visible}) + withheld({withheld}) != total({total})",
            )
        ]
    return []
