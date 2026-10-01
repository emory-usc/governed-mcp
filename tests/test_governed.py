"""Core invariant tests for governed_mcp."""

from governed_mcp import data, guardrails
from governed_mcp.core import aggregate_balances, query_accounts, query_customers
from governed_mcp.models import CallerClaims, Severity

ADMIN = CallerClaims(sub="admin", roles=["admin"])
RM01 = CallerClaims(sub="rm-01", roles=["rm"], rm_id="rm-01")
NONE = CallerClaims(sub="anon", roles=[])


def test_admin_sees_everything():
    r = query_customers(ADMIN)
    assert r.visible_count == r.total_count == len(data.all_customers())
    assert r.withheld_count == 0
    assert not r.blocked


def test_rm_isolation():
    r = query_customers(RM01)
    assert r.visible_count > 0
    assert all(row["rm_id"] == "rm-01" for row in r.rows)
    assert r.withheld_count > 0


def test_fail_closed():
    r = query_customers(NONE)
    assert r.visible_count == 0
    assert r.withheld_count == r.total_count


def test_account_numbers_are_masked():
    r = query_accounts(ADMIN)
    assert len(r.rows) > 0
    assert all(not row["account_number"].startswith("ACCT-") for row in r.rows)


def test_restricted_field_never_published():
    r = query_customers(ADMIN)
    assert all("tax_id" not in row for row in r.rows)


def test_count_integrity():
    for claims in (ADMIN, RM01, NONE):
        r = query_accounts(claims)
        assert r.visible_count + r.withheld_count == r.total_count


def test_nonexistent_segment_returns_empty():
    r = query_customers(ADMIN, segment="nope")
    assert r.total_count == 0 and r.rows == []


def test_guardrail_blocks_restricted_field():
    bad_row = {"id": "cust-x", "name": "X", "tax_id": "TAX-1"}
    findings = guardrails.check_rows([bad_row], "customers")
    assert any(f.code == "restricted_field_leak" and f.severity == Severity.BLOCKING for f in findings)


def test_guardrail_blocks_unmasked_account_number():
    bad_row = {"id": "acct-x", "account_number": "ACCT-9999"}
    findings = guardrails.check_rows([bad_row], "accounts")
    assert any(f.code == "unmasked_account_number" for f in findings)


def test_aggregate_is_entitled():
    agg = aggregate_balances(RM01, group_by="region")
    # rm-01 only sees one region's customers, so at most one group has balance
    assert len(agg.rows) >= 1
    assert agg.withheld_count > 0
