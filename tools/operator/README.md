# Operator — the executor

The Operator is the pipeline's **executor**: it moves material along the
stages and is the only role that writes canonical notes — exclusively
through the gated promotion path.

## Powers

- Run the non-canonical loop: `gf loop` (triage → steward → review).
- Bridge steward packets to the human review surface: `gf review`.
- Build pending proposals from human decisions: `gf propose`
  (issues the approval token).
- Apply proposals with a valid token: `gf apply` → canonical note +
  manifest.
- Quarantine candidates: `gf quarantine`.
- Roll back a promotion run via its manifest: `gf rollback`.

## Hard limits (enforced in `ghostforge/promotion.py`)

- Canonical mutation happens **only** in `gf apply`, and only with an
  approval token that verifies (HMAC over the exact proposal content,
  expiry-checked). Tampered proposals invalidate their tokens.
- Source hash must re-verify against the live file at apply time.
  Unknown/unverifiable data is unsafe, never "zero".
- Targets must be registered in `canonical_targets`.
- Append-only: existing canonical targets are refused unless the decision
  explicitly supersedes.
- Quarantined material never auto-promotes.

## The split

The Operator never *discovers* truth — it only executes the human's
decisions under the token gate. Discovery belongs to the observer
(`tools/shadow-steward/`). No single automated component can both find
something and declare it true.

## Operation

```bash
gf loop --vault /path/to/vault                 # headless-safe stages
gf decide --candidate <id> --vault ...         # scaffold (human edits)
gf propose --decision <file> --vault ...       # pending proposal + token
gf apply --proposal <p> --token <t> --vault ...# gated canonical write
```
