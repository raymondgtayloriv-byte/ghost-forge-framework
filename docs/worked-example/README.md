# Worked Example: Harborlight

A synthetic end-to-end run of the pipeline, produced by the shipped `gf`
CLI — every file under `artifacts/` is real output, not hand-written.
Harborlight is fictional; the commands are the actual interface.

Reproduce it: set `GHOST_FORGE_PROMOTION_SECRET` to any demo value and run
`python3 tools/gen_worked_example.py` (it builds a throwaway vault in
`/tmp` and snapshots the outputs here).

## The story

The Harborlight relay team captures three pieces of material:

1. A raw capture: beacon p99 latency measured at 840ms (observation, not
   yet a claim).
2. A raw capture: an unverified rumor about a hardware fault.
3. A signed agent update: the agreed beacon retry policy
   (`artifacts/01-agent-update-beacon.md`) — filed via
   `gf intake-update`, which enforces the closeout contract.

A fourth note *claims* `canonical_truth: true` without going through
promotion. Watch what the pipeline does with it.

## Step 1 — Triage (draft only)

```
gf loop        # triage → steward → review, nothing canonical
```

The deterministic triage worker classifies the inbox and writes a draft
digest: `artifacts/02-triage-digest/`. Note the frontmatter:
`canonical_truth: false`, `source_class: triage_draft` — drafts are never
canonical and are excluded from autonomous promotion.

## Step 2 — Steward evidence (read-only)

The observer collects the evidence roots into a timestamped packet:
`artifacts/03-steward-packet.md` (hashes and provenance live in the
packet's `packet.json`). The steward wrote nothing canonical — it can't.

## Step 3 — Review surface

The bridge produces one review packet per candidate plus the approval
slate: `artifacts/04-approval-slate.md`. The beacon policy's packet is
`artifacts/05-review-packet-beacon.md` — evidence, proposed actions,
and where to record the decision.

The note that claimed canonical status went to the **exception queue**:
`artifacts/06-exception-fake-canonical.md`. The pipeline refuses to
re-promote something already marked canonical without human confirmation.

## Step 4 — Human decision → proposal → gated apply

```
gf decide --candidate <beacon-id>     # scaffold the decision JSON
# (human edits: action=promote, title, body, rationale)
gf propose --decision <file>          # pending proposal + approval token
gf apply --proposal <p> --token <t>   # gated canonical write
```

Decision: `artifacts/07-decision-promote.json`. Proposal summary:
`artifacts/08-proposal-beacon.md`. The apply verified the token (HMAC
over the exact proposal), re-verified the source hash, confirmed the
target is registered, and wrote the canonical note —
`artifacts/09-canonical-note.md` — with full provenance
(`promoted_from`, `source_hash`, `promotion_run`, `approved_by: human`),
plus a manifest so the run can be rolled back.

## Step 5 — Quarantine branch

The rumor was decided `quarantine`, proposed, and applied through the same
token gate: `artifacts/10-quarantine-rumor.md`. Quarantined material is
preserved with its reason and never auto-promotes.

## What this demonstrates

- The observer/executor split: collection never touches canonical truth;
  the executor only acts under the token gate.
- The human gate is structural, not advisory: no token, no canonical write.
- Drafts, packets, and review surfaces are all explicitly non-canonical.
- The quarantine and exception paths are first-class, not afterthoughts.
- Unknown/unverified material is unsafe, never "zero" — the rumor and the
  fake-canonical note were both refused the canonical path for different
  documented reasons.

Timestamps and run IDs in the artifacts are from the generation run;
re-running the script produces the same structure with fresh IDs.
