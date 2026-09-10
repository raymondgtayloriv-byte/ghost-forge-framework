# Promotion Doctrine

The rules that govern how draft material becomes canonical truth. They are
enforced by `ghostforge/promotion.py`, not by convention.

## 1. Canonical mutation is gated

Canonical notes are written **only** by `gf apply`, and only with an
approval token that verifies: HMAC-SHA256 over the proposal's exact
content, bound to an expiry. A tampered proposal invalidates its token.
Intake, triage, steward collection, review packets, and proposal building
are explicitly non-token paths — the token gates *canonical mutation*,
not every write.

## 2. Provenance is mandatory

Every canonical note records `promoted_from`, `source_hash`,
`promotion_run`, `decision_id`, and `approved_by`. A note without
provenance is not canonical, whatever its frontmatter claims.

## 3. Unknown data is unsafe, never "zero"

If the source hash cannot be re-verified against the live file at apply
time, the apply is refused. Unavailable or unverifiable data is treated
as a risk, never as "no risk".

## 4. Append-only

A canonical target that already exists is refused unless the decision
explicitly supersedes it. Corrections are new notes that link back
(`supersedes:`); history is never edited in place. Rollback removes files
created by a run per its manifest — it never rewrites canonical content.

## 5. Registered targets only

`canonical_targets` in config lists where canonical notes may live
(default: `030 Projects`, `020 Daily`). Apply to anything else is refused.

## 6. Quarantine first

Material that is contradictory, low-confidence, sensitive, or risky goes
to quarantine with a reason, not to canonical. Quarantined material is
never auto-promoted.

## 7. The human is the gate; the autonomous lane is the exception

By default, every promotion requires a human decision and a human-held
approval token. The experimental autonomous lane (`ghostforge/autonomous.py`)
is **disabled by default** and **dry-run by default**. When explicitly
enabled, it may promote only: hash-verified, non-sensitive, high-confidence
agent updates to registered targets — promoting their verbatim source
content, never authored content — and every such promotion is recorded as
`decided_by: "autonomous-lane"` with its gate evidence. Triage drafts,
generated material, and unverified sources are excluded by construction.

## 8. Secrets never enter the vault

The promotion secret lives in an environment variable, never in notes,
config, or the repo. Tokens expire. Losing the secret invalidates old
tokens; it does not corrupt the vault.
