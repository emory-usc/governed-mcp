"""Domain models: caller identity, query results, and guardrail findings."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CallerClaims(BaseModel):
    """Identity + entitlements presented by the caller on each request."""

    sub: str = Field(description="Subject id — user or service principal")
    roles: list[str] = Field(default_factory=list, description="Entitlement roles, e.g. ['rm']")
    rm_id: str | None = Field(default=None, description="Relationship-manager id (role=rm)")
    region: str | None = Field(default=None, description="Region (role=regional_director)")


class Severity(str, Enum):
    BLOCKING = "blocking"
    WARNING = "warning"


class Finding(BaseModel):
    """A guardrail finding. Blocking findings withhold the result."""

    code: str
    severity: Severity
    message: str


class QueryResult(BaseModel):
    """The envelope every tool returns — rows plus the honesty disclosure."""

    entity: str
    rows: list[dict[str, Any]] = Field(default_factory=list)
    total_count: int = Field(default=0, description="Rows matching the caller's filter, before RLS")
    visible_count: int = Field(default=0)
    withheld_count: int = Field(default=0, description="Rows hidden by entitlement (disclosed, not silent)")
    blocked: bool = Field(default=False, description="True when a guardrail withheld the whole result")
    blocked_reason: str | None = None
    filters_applied: dict[str, Any] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)
    dataset_version: str = ""
