# Security Policy

## Reporting a vulnerability

Report security issues privately rather than opening a public issue. Include a
description, reproduction steps, and any proposed fix. Do not include real
customer data or credentials in any report.

## Security posture

- **Read-only by construction.** The MCP surface has no write tools — the model
  can only describe and read published entities; it cannot create, update, or
  delete anything.
- **Fail-closed row-level security.** Unknown or missing entitlements resolve to
  an empty result, never somebody else's data.
- **Two independent boundaries.** Row-level filtering (application code) and
  deterministic guardrails (PII masking, field allow-list, count integrity) run
  separately and fail differently. A blocking guardrail finding withholds the
  whole result.
- **Honest disclosure.** Results report a `withheld_count` when entitlements hide
  rows, so an agent can tell "no data" from "data I can't see."
- **Synthetic data only.** The bundled dataset is generated from constants; no
  real customer data is involved.
- **No secrets in the image or repo.** The server is stateless; caller identity
  is supplied per request. Production token verification is documented in
  `docs/architecture.md`.

## Supported versions

Only the latest `main` branch is supported for security fixes.
