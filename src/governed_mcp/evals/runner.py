"""Adversarial eval harness — proves the boundaries hold.

Nine cases across four families: leakage, fabrication, disclosure, grounding.
Each case exercises the core directly with a specific caller identity and
asserts an invariant. The runner exits non-zero if any case fails.
"""

from __future__ import annotations

from rich import box
from rich.console import Console
from rich.table import Table

from governed_mcp import data
from governed_mcp.core import aggregate_balances, query_accounts, query_customers
from governed_mcp.models import CallerClaims

console = Console()

ADMIN = CallerClaims(sub="admin", roles=["admin"])
RM01 = CallerClaims(sub="rm-01", roles=["rm"], rm_id="rm-01")
NORTH = CallerClaims(sub="north-dir", roles=["regional_director"], region="north")
NONE = CallerClaims(sub="anon", roles=[])


def _leakage_rm_isolation():
    r = query_customers(RM01)
    bad = [row for row in r.rows if row["rm_id"] != "rm-01"]
    ok = not bad and r.visible_count > 0 and r.withheld_count > 0
    return ok, f"{r.visible_count} visible, {r.withheld_count} withheld; cross-rm rows: {len(bad)}"


def _leakage_regional_isolation():
    r = query_customers(NORTH)
    bad = [row for row in r.rows if row["region"] != "north"]
    ok = not bad and r.visible_count > 0 and r.withheld_count > 0
    return ok, f"{r.visible_count} visible, {r.withheld_count} withheld; cross-region rows: {len(bad)}"


def _leakage_fail_closed():
    r = query_customers(NONE)
    ok = r.visible_count == 0 and r.withheld_count == r.total_count and r.total_count > 0
    return ok, f"visible={r.visible_count} withheld={r.withheld_count} total={r.total_count}"


def _leakage_restricted_field_never_published():
    r = query_customers(ADMIN)
    leaked = [row for row in r.rows if "tax_id" in row]
    ok = not leaked and r.visible_count == r.total_count
    return ok, f"{r.visible_count} rows; rows with tax_id: {len(leaked)}"


def _fabrication_nonexistent_empty():
    r = query_customers(ADMIN, segment="does-not-exist")
    ok = r.total_count == 0 and r.rows == []
    return ok, f"total={r.total_count} rows={len(r.rows)}"


def _fabrication_source_verified():
    r = query_accounts(ADMIN)
    ids = {a["id"] for a in data.all_accounts()}
    missing = [row for row in r.rows if row["id"] not in ids]
    ok = not missing and len(r.rows) == len(ids)
    return ok, f"{len(r.rows)} rows; unsourced rows: {len(missing)}"


def _disclosure_withheld_honest():
    r = query_accounts(RM01)
    ok = r.visible_count + r.withheld_count == r.total_count and r.withheld_count > 0
    return ok, f"visible={r.visible_count} withheld={r.withheld_count} total={r.total_count}"


def _disclosure_masked_accounts():
    r = query_accounts(ADMIN)
    bad = [row for row in r.rows if str(row["account_number"]).startswith("ACCT-")]
    ok = not bad and len(r.rows) > 0
    return ok, f"{len(r.rows)} rows; unmasked account numbers: {len(bad)}"


def _grounding_dataset_version():
    r = query_customers(ADMIN)
    ok = bool(r.dataset_version) and r.dataset_version == "2026.10.1"
    return ok, f"dataset_version={r.dataset_version!r}"


def _grounding_aggregate_consistency():
    agg = aggregate_balances(ADMIN, group_by="region")
    ok = all("group" in row and "total_balance" in row for row in agg.rows) and len(agg.rows) > 0
    return ok, f"{len(agg.rows)} groups"


CASES = [
    ("leakage", "rm_isolation", _leakage_rm_isolation),
    ("leakage", "regional_isolation", _leakage_regional_isolation),
    ("leakage", "fail_closed", _leakage_fail_closed),
    ("leakage", "restricted_field_never_published", _leakage_restricted_field_never_published),
    ("fabrication", "nonexistent_empty", _fabrication_nonexistent_empty),
    ("fabrication", "source_verified", _fabrication_source_verified),
    ("disclosure", "withheld_honest", _disclosure_withheld_honest),
    ("disclosure", "masked_accounts", _disclosure_masked_accounts),
    ("grounding", "dataset_version", _grounding_dataset_version),
    ("grounding", "aggregate_consistency", _grounding_aggregate_consistency),
]


def run_all() -> bool:
    table = Table(box=box.ROUNDED, title="Governed MCP — adversarial eval")
    table.add_column("Family")
    table.add_column("Case")
    table.add_column("Result", justify="center")
    table.add_column("Detail")

    all_ok = True
    passed = 0
    for family, name, fn in CASES:
        try:
            ok, detail = fn()
        except Exception as exc:  # noqa: BLE001
            ok, detail = False, f"raised {type(exc).__name__}: {exc}"
        all_ok = all_ok and ok
        passed += 1 if ok else 0
        table.add_row(family, name, "[green]PASS[/]" if ok else "[red]FAIL[/]", detail)

    console.print(table)
    console.print(
        f"\n{'[green]ALL PASS[/]' if all_ok else '[red]FAILURES PRESENT[/]'} — "
        f"{passed}/{len(CASES)} cases"
    )
    return all_ok
