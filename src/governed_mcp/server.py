"""MCP server — the delivery surface.

A thin layer over :mod:`governed_mcp.core`. Tools are read-only and typed;
caller identity flows in through a context variable (set by an auth layer in
production, or defaulted to the dev caller locally). All governance lives in
the core, so this module stays trivial.
"""

from __future__ import annotations

import contextvars
from typing import Any

from governed_mcp.config import get_settings
from governed_mcp.core import aggregate_balances as _agg
from governed_mcp.core import describe_schema as _describe_schema
from governed_mcp.core import query_accounts as _accts
from governed_mcp.core import query_customers as _custs
from governed_mcp.models import CallerClaims

_current_claims: contextvars.ContextVar[CallerClaims] = contextvars.ContextVar(
    "governed_claims", default=None
)


def set_caller(claims: CallerClaims | dict) -> None:
    """Set the caller for the current context (used by tests and the auth layer)."""
    if isinstance(claims, dict):
        claims = CallerClaims(**claims)
    _current_claims.set(claims)


def _claims() -> CallerClaims:
    c = _current_claims.get()
    if c is not None:
        return c
    return CallerClaims(**get_settings().dev_claims())


def create_mcp():
    """Build the MCP server. ``mcp`` is imported lazily (core runs without it)."""
    from mcp.server.mcpserver import MCPServer

    mcp = MCPServer(name="governor-mcp")

    @mcp.tool()
    def query_customers(segment: str | None = None, region: str | None = None) -> dict[str, Any]:
        """List customers visible to the caller, with optional filters.

        Returns rows plus a withheld_count disclosure when entitlements hide rows.
        """
        return _custs(_claims(), segment=segment, region=region).model_dump()

    @mcp.tool()
    def query_accounts(
        customer_id: str | None = None,
        account_type: str | None = None,
        min_balance: float | None = None,
    ) -> dict[str, Any]:
        """List accounts visible to the caller. Account numbers are masked."""
        return _accts(
            _claims(),
            customer_id=customer_id,
            account_type=account_type,
            min_balance=min_balance,
        ).model_dump()

    @mcp.tool()
    def aggregate_balances(group_by: str = "region") -> dict[str, Any]:
        """Aggregate balances over the caller's visible accounts (region/segment/type)."""
        return _agg(_claims(), group_by=group_by).model_dump()

    @mcp.tool()
    def describe_schema() -> dict[str, Any]:
        """Describe the published data surface and available tools."""
        return _describe_schema()

    return mcp
