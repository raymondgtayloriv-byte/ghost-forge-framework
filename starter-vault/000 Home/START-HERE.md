# START HERE — Ghost Forge Framework (starter vault)

This is a **review-gated memory/source-truth system for teams of AI agents**.
It exists to solve one problem: when several agents write into the same
vault, *draft material* must never be mistaken for *canonical truth*.

## The pipeline

```
capture → triage → steward evidence → review packet
        → human decision → promotion proposal → gated canonical apply
                                                     ↘ quarantine
```

- **Capture** (`010 Inbox/`): raw captures and agent updates land here.
  Nothing in the inbox is canonical truth.
- **Triage**: a deterministic worker classifies inbox material into lanes
  and writes *draft* digests. Drafts are never canonical.
- **Steward** (observer): read-only collection. It walks the evidence
  roots, records hashes and provenance, and writes timestamped evidence
  packets to `00_System/Packets/`. It cannot promote anything.
- **Review** (bridge): steward packets become human-readable review
  packets in `010 Inbox/Review Packets/`, plus an approval slate and an
  exception queue. Still nothing canonical.
- **Human decision**: you record a decision JSON per candidate
  (`promote` / `quarantine` / `defer`).
- **Proposal**: `gf propose` builds a pending proposal and issues an
  **approval token** bound to its exact content.
- **Gated apply**: `gf apply` verifies the token, the source hash, and the
  registered target, then writes the canonical note — append-only, with a
  manifest so the run can be rolled back.

## The one rule

> **Canonical mutation happens only through the gated promotion path,
> and only with a valid approval token.**

Everything else — intake, triage, steward collection, review packets,
proposals, status — is explicitly non-canonical.

## Where things live

| Lane | Purpose |
|---|---|
| `010 Inbox/Raw Captures/` | Unverified captures |
| `010 Inbox/Agent Raw Notes/` | Draft agent notes (not yet contract-valid) |
| `010 Inbox/Agent_Updates/` | Signed, contract-valid agent updates (`YYYY-MM-DD/`) |
| `010 Inbox/02_Digests/` | Triage digests (draft only) |
| `010 Inbox/Review Packets/` | Human decision surface + approval slate |
| `010 Inbox/Exception Queue/` | Items needing human eyes |
| `010 Inbox/Decisions/` | Human decision JSONs |
| `020 Daily/` | Daily notes (canonical target) |
| `030 Projects/` | Project notes (canonical target) |
| `040 Agent Instructions/` | The contracts agents follow |
| `050 Workflows/` | Pipeline documentation |
| `060 References/Templates/` | Note templates |
| `070 Archive/` | Quarantine + archive |

## First run

```bash
pip install -e .
export GHOST_FORGE_PROMOTION_SECRET="$(openssl rand -hex 32)"
gf init --vault ./my-vault
gf status --vault ./my-vault
```

Then read `040 Agent Instructions/closeout-contract.md` before filing
your first agent update, and `docs/worked-example/` for the full loop.
