# Architecture

Ghost Forge is a **review-gated memory/source-truth system for teams of AI
agents**. It answers one question: when several agents write into the same
vault, how do you keep *draft material* from being mistaken for *canonical
truth*?

## The core split: observer vs. executor

Two halves with opposite powers:

- **The observer (Shadow Steward)** can read the configured evidence
  roots (raw captures, agent updates, triage digests) and write evidence
  packets. It cannot write canonical notes and cannot promote anything.
  Read-only by construction.
- **The executor (Operator)** moves material along the pipeline and is
  the only writer of canonical notes — but only through the gated
  promotion path, and only with a valid approval token.

Splitting them means no automated component *finds* something and
*declares it true* on its own. The default path to canonical truth runs
through human review and the token gate. The one explicit exception is
the experimental autonomous lane (disabled and dry-run by default, with
stricter eligibility gates): enabling it delegates the decision role to
the lane, and its promotions carry `autonomous-lane` provenance so they
are never mistaken for human approvals. The token still protects
proposal integrity at apply time, but it is not proof of a human
decision in the autonomous case.

## The pipeline

```
capture → triage → steward evidence → review packet
        → human decision → promotion proposal → gated canonical apply
                                                     ↘ quarantine
```

1. **Capture.** Raw captures and signed agent updates land in `010 Inbox/`.
   Nothing here is canonical.
2. **Triage.** A deterministic worker classifies inbox material and writes
   draft digests. Drafts are never canonical and are excluded from
   autonomous promotion.
3. **Steward evidence.** The observer walks the exact evidence roots
   (raw captures, agent updates, triage digests), records SHA-256 hashes
   and provenance, and writes timestamped evidence packets to
   `00_System/Packets/`. No canonical writes, no archive reads, no network.
4. **Review packet.** The review bridge turns packets into a human decision
   surface: one review packet per candidate, an approval slate, and an
   exception queue for low-confidence, contradictory, or risky items.
5. **Human decision.** A decision JSON per candidate: `promote`,
   `quarantine`, or `defer`, with rationale.
6. **Promotion proposal.** `gf propose` builds a pending proposal and
   issues an **approval token** — an HMAC bound to the proposal's exact
   content, with an expiry.
7. **Gated canonical apply.** `gf apply` verifies the token, re-verifies
   the source hash, checks the target is registered, and enforces
   append-only writes. It records a manifest so the run can be rolled back.

The **quarantine branch** removes a candidate to `070 Archive/Quarantine/`
with a reason. Quarantined material never auto-promotes.

## What "canonical" means here

A canonical note is a note the system treats as trusted: it was
human-approved, its provenance is recorded (`promoted_from`,
`source_hash`, `promotion_run`, `decision_id`), and it is append-only —
corrections are new notes that supersede, never in-place edits.
`canonical_truth: true` in frontmatter is a *claim the pipeline makes*,
not a flag anyone can set by hand: only the gated apply path writes it.

## What this is not

- Not a vector database, not RAG, not a chat memory plugin. It's a
  **write-path discipline** for agent fleets: the value is in what *can't*
  happen (silent promotion, lost provenance, overwritten history).
- Not macOS-only. The reference scheduler is launchd/cron; the framework
  itself is OS-neutral Python.

## Implementation map

| Concept | Code |
|---|---|
| Vault layout, frontmatter, config | `ghostforge/vault.py` |
| Intake + closeout contract | `ghostforge/intake.py` |
| Triage worker (+ model adapter seam) | `ghostforge/triage.py` |
| Observer (Shadow Steward) | `ghostforge/steward.py` |
| Review bridge | `ghostforge/review.py` |
| Gated promotion engine | `ghostforge/promotion.py` |
| Experimental autonomous lane | `ghostforge/autonomous.py` |
| CLI | `ghostforge/cli.py` (`gf`) |

`tools/shadow-steward/` and `tools/operator/` document the two suites as
operational roles over the same CLI.
