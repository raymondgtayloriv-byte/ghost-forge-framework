# Roles and Boundaries (model-agnostic)

These are **roles**, not models. Bind whichever model or tool fits each
role; the contracts stay the same.

## Controller (human)

- Owns the vault. The only role that can approve canonical mutation.
- Writes decision JSONs, issues approvals via tokens, resolves the
  exception queue.

## Bounded executor

- Does the work described in a decision or task; writes agent updates per
  the closeout contract.
- Cannot promote anything. Its output is evidence.

## Triage worker

- Cheap first pass over the inbox: classify, extract, draft.
- Output is draft-only (`canonical_truth: false`), excluded from
  autonomous promotion.
- Shipped default is deterministic rules; a cheap model may plug into the
  documented adapter with the same output contract.

## Observer / Steward

- Read-only collection over the evidence roots.
- Writes timestamped evidence packets. No canonical writes, no promotion,
  no archive reads, no network.

## Operator

- Moves material along the pipeline: triage → steward → review →
  proposal → gated apply.
- The *only* writer of canonical notes, and only through `gf apply` with
  a valid approval token.

## Human approver

- Reviews the approval slate, decides promote / quarantine / defer.
- In small deployments this is the same person as the controller.

## What no role may do

- Treat inbox material, triage drafts, or packets as canonical truth.
- Promote without the token gate (except the experimental autonomous
  lane, which is disabled by default and auditable).
- Store secrets in the vault. Secrets live in the environment, never in notes.
