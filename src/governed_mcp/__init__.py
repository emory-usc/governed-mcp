"""Governed MCP — a read-only MCP server with row-level security and guardrails.

The core idea: give an AI agent a *governed* window onto data. Typed, read-only
tools expose a published field surface; every request carries caller claims that
drive per-caller row filtering (fail-closed); and a deterministic guardrail layer
runs in code, independent of the data boundary, to block anything that would
leak. An eval harness proves the boundaries hold against adversarial cases.
"""

__version__ = "0.1.0"
