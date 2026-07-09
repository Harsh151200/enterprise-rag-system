# Semantic Versioning and Pre-release Policy

## Scope
This repository follows [Semantic Versioning 2.0.0](https://semver.org/) for all tagged releases.

## Version Format
`MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]`

- **MAJOR**: increment for incompatible API or behavior changes.
- **MINOR**: increment for backward-compatible feature additions.
- **PATCH**: increment for backward-compatible bug fixes.

## Pre-release Rules
- Use pre-release identifiers before stable milestones (for example `v3.0.0-alpha`).
- Supported identifiers and order:
  1. `alpha`
  2. `beta`
  3. `rc`
- Numeric suffixes indicate iteration order (for example `v3.0.0-alpha.1`, `v3.0.0-alpha.2`).

## Stability and Promotion
- `alpha`: active development, incomplete scope allowed.
- `beta`: feature-complete candidate, stabilization focus.
- `rc`: release candidate, only blocker fixes.
- stable (`vX.Y.Z`): production-ready release.

## Release Guardrails
- Every release must include:
  - a changelog entry,
  - a release checklist completion record,
  - Definition of Done sign-off,
  - rollback plan confirmation.

## Backporting
- Critical fixes to an existing stable line use patch bumps on that line.
- Do not add new features to patch backports.
