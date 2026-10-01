"""Entitlement resolution and row-level filtering (fail-closed).

A caller's claims resolve to an Entitlement scope. Unknown or missing
entitlements resolve to ``none`` — the caller sees zero rows, never somebody
else's data. This is the first, independent boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

from governed_mcp.models import CallerClaims


@dataclass(frozen=True)
class Entitlement:
    scope: str  # "all" | "region" | "rm" | "none"
    region: str | None = None
    rm_id: str | None = None


def resolve(claims: CallerClaims) -> Entitlement:
    roles = {r.lower() for r in claims.roles}
    if "admin" in roles:
        return Entitlement("all")
    if "regional_director" in roles and claims.region:
        return Entitlement("region", region=claims.region)
    if "rm" in roles and claims.rm_id:
        return Entitlement("rm", rm_id=claims.rm_id)
    return Entitlement("none")


def customer_visible(ent: Entitlement, customer: dict) -> bool:
    if ent.scope == "all":
        return True
    if ent.scope == "region":
        return customer["region"] == ent.region
    if ent.scope == "rm":
        return customer["rm_id"] == ent.rm_id
    return False


def visible_customer_ids(ent: Entitlement) -> set[str]:
    from governed_mcp import data

    return {c["id"] for c in data.all_customers() if customer_visible(ent, c)}
