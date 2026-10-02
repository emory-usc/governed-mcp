# Architecture

## What this is

`governor-mcp` is a **read-only MCP server with per-caller row-level security and
deterministic guardrails**. It gives an AI agent a *governed* window onto a data
surface: the agent can ask questions and read published fields, but it cannot
write, cannot reach unpublished fields, and cannot see rows it isn't entitled to
— and when data *is* hidden, the result says so rather than silently omitting it.

## The core idea: two independent boundaries

The security model is two layers that fail differently.

```
        ┌─────────────────────────────────────────────┐
        │                  caller claims               │
        └──────────────────────┬──────────────────────┘
                               │
                 1. Entitlement boundary (RLS)
        ┌──────────────────────▼──────────────────────┐
        │  resolve claims -> scope (all/region/rm/   │
        │  none); filter rows; count what was hidden  │
        └──────────────────────┬──────────────────────┘
                               │  visible rows + withheld_count
                 2. Guardrail boundary (deterministic)
        ┌──────────────────────▼──────────────────────┐
        │  publish allow-listed fields; mask account  │
        │  numbers; verify counts; block on violation │
        └──────────────────────┬──────────────────────┘
                               │
                      QueryResult (rows, withheld_count,
                      blocked, findings, dataset_version)
```

1. **Entitlement boundary** (application code, `entitlements.py`) resolves the
   caller's claims to a scope and filters rows. Missing/unknown claims resolve to
   `none` — the caller sees zero rows. Rows hidden by this boundary are *counted*
   and disclosed, never silently dropped.

2. **Guardrail boundary** (`guardrails.py`) runs on the already-filtered result
   and is independent of the first: it publishes only allow-listed fields, masks
   account numbers, verifies `visible + withheld == total`, and returns a
   blocking finding if a restricted field or unmasked PII somehow appears.

Because the two boundaries are separate, a bug in one does not silently bypass
the other — and the eval harness asserts both hold.

## Determinism and fabrication

No LLM runs inside the tool path. Tools are pure functions over a synthetic
dataset: a query for a nonexistent segment returns zero rows, not invented data.
Fabrication is structurally impossible; the guardrails verify it anyway
(source-verified row IDs, no unsourced fields).

## Caller identity

- **Dev mode** (default): identity comes from `GOVERNED_DEV_CALLER` (or the
  `--caller` concept in tests), so the whole thing runs offline.
- **Token mode** (`GOVERNED_AUTH_MODE=token`): identity is extracted from the
  `Authorization` bearer token. The server verifies a JWT against
  `GOVERNED_JWT_ISSUER` / `GOVERNED_JWT_AUDIENCE`; in a production deployment the
  token is minted by an identity provider (e.g. Entra ID) and carries the roles
  (`rm`, `regional_director`, `admin`) that drive entitlements.

The mapping from roles to data scopes is explicit in `entitlements.resolve`:
`admin` → all, `regional_director` + region → one region, `rm` + `rm_id` → one
relationship manager's book, anything else → none.

## The synthetic dataset

`data.py` generates 36 customers (6 regions × 6, one relationship manager per
region) and ~72 accounts deterministically from constants. Every customer has a
restricted `tax_id` that is never published; account numbers are masked to
`****-NNNN` on publish. Nothing is real customer data.

## The eval harness

`governed eval` runs ten cases across four families — leakage (cross-rm and
cross-region isolation, fail-closed, restricted-field never published),
fabrication (nonexistent-empty, source-verified), disclosure (withheld honesty,
masked accounts), and grounding (dataset version, aggregate consistency). It
exits non-zero if any case fails, and it runs in CI as a deploy gate.

## Deployment

`infra/main.bicep` deploys a single stateless Container App (streamable HTTP on
8000, scale-to-zero, TCP liveness probe) with Application Insights. There is no
database and no secret store — the server holds no state. Production hardening
(token-mode auth, VNet ingress, an API gateway in front) is the natural next
step and is documented rather than hidden.
