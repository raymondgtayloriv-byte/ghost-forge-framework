# Ghost Forge Framework

**A review-gated memory/source-truth system for teams of AI agents.**

When several AI agents write into the same vault, draft material gets
mistaken for canonical truth. Ghost Forge fixes that with an
**observer/executor split**:

- The **observer** (Shadow Steward) sees everything and can change nothing
  canonical. It collects evidence read-only into timestamped packets.
- The **executor** (Operator) moves material through review toward truth —
  but the *only* way anything becomes canonical is a **human-approved,
  token-gated promotion**.

No single automated component can both *find* something and *declare it
true*. The human gate sits structurally between them.

```
capture → triage → steward evidence → review packet
        → human decision → promotion proposal → gated canonical apply
                                                     ↘ quarantine
```

## Quickstart

```bash
pip install -e .   # or: pip install git+https://github.com/raymondgtayloriv-byte/ghost-forge-framework.git
export GHOST_FORGE_PROMOTION_SECRET="$(openssl rand -hex 32)"

gf init --vault ./my-vault
gf capture --project harborlight --title "Beacon latency observation" \
  --body "p99 at 840ms in the synthetic load run."
gf loop --vault ./my-vault          # triage → steward → review (never canonical)
gf status --vault ./my-vault
```

Then open the approval slate the loop built
(`010 Inbox/Review Packets/_slate.md`), decide each candidate, and promote:

```bash
gf decide --candidate <id> --vault ./my-vault
# edit the decision JSON: action=promote, title, body, rationale
gf propose --decision <file> --vault ./my-vault     # issues the approval token
gf apply --proposal <p> --token <t> --vault ./my-vault
```

## Why this exists

AI agent fleets are great at producing material and terrible at
governing it. Notes contradict each other, "verified" means whatever the
last writer felt, and history gets silently overwritten. Ghost Forge is a
**write-path discipline**:

1. **Nothing in the inbox is canonical.** Raw captures, agent updates,
   triage drafts — all evidence, all explicitly `canonical_truth: false`.
2. **The steward can't promote.** Read-only collection with hashes and
   provenance; the worst a bad observer can do is write a bad packet.
3. **Canonical mutation is token-gated.** `gf apply` verifies an HMAC
   approval token bound to the proposal's exact content, re-verifies the
   source hash, checks the target is registered, and writes append-only —
   with a manifest, so the run rolls back cleanly.
4. **Quarantine is first-class.** Contradictory, risky, or unverified
   material goes to quarantine with a reason instead of silently dying —
   or silently shipping.

## What's here

| Path | What |
|---|---|
| `ghostforge/` | The framework: intake, triage, steward, review bridge, promotion engine, experimental autonomous lane, `gf` CLI |
| `starter-vault/` | A working vault skeleton: lanes, closeout contract, roles, 18 templates, example config |
| `docs/architecture.md` | The observer/executor design, fresh |
| `docs/promotion-doctrine.md` | The 8 rules governing canonical truth |
| `docs/roles.md` | Model-agnostic roles and suggested bindings |
| `docs/triage.md`, `docs/scheduling.md` | Triage worker and scheduler adapter boundary |
| `docs/privacy.md` | Structural privacy guarantees |
| `docs/worked-example/` | Harborlight: a full synthetic run with real CLI-produced artifacts |
| `tools/shadow-steward/`, `tools/operator/` | The two suites as operational roles |
| `tests/` | 18 tests over the full loop: contract, gating, rollback, quarantine |

One dependency: PyYAML. Python 3.10+.

## The autonomous lane (experimental)

A conservative autonomous path exists for high-confidence,
hash-verified, non-sensitive agent updates — **disabled by default** and
**dry-run by default**. Triage drafts, generated material, and unverified
sources are excluded by construction. Every autonomous promotion is
recorded as `decided_by: "autonomous-lane"` with its gate evidence, so
it's auditable and distinguishable from human approvals. See
`docs/promotion-doctrine.md` rule 7.

## Status

v0.1.0 — initial public release. The framework is a clean-room public
implementation of the documented contracts: fresh code, synthetic
examples, no private history.
