# Pipeline Overview

The pipeline is an assembly line. Material flows one direction; each stage
adds structure and none of the early stages can write canonical truth.

```
                        ┌──────────────┐
  raw material ───────▶ │ 01 · CAPTURE │  010 Inbox/Raw Captures, Agent_Updates
                        └──────┬───────┘
                               │ classify, extract, draft
                        ┌──────▼───────┐
                        │ 02 · TRIAGE  │  deterministic worker → 02_Digests
                        └──────┬───────┘
                               │ read-only collect + hash
                        ┌──────▼───────┐
                        │ 03 · STEWARD │  observer → 00_System/Packets
                        └──────┬───────┘
                               │ bridge to human surface
                        ┌──────▼───────┐
                        │ 04 · REVIEW  │  Review Packets + slate + exceptions
                        └──────┬───────┘
                               │ human decision (promote/quarantine/defer)
                        ┌──────▼───────┐
                        │ 05 · DECIDE  │  010 Inbox/Decisions/*.json
                        └──────┬───────┘
                               │ build proposal + issue approval token
                        ┌──────▼───────┐
                        │ 06 · PROPOSE │  00_System/Proposals (pending)
                        └──────┬───────┘
                               │ verify token + source hash + target
                        ┌──────▼───────┐
                        │ 07 · APPLY   │  canonical note + manifest
                        └──────────────┘
```

The quarantine branch leaves the line at stage 05/06: quarantined material
goes to `070 Archive/Quarantine/` with a reason and never auto-promotes.

Stages 01–04 and 06 are runnable headless on a schedule
(`gf loop` covers 02–04). Stages 05 and 07 require the human.
The experimental autonomous lane (disabled by default) may move
high-confidence, hash-verified, non-sensitive agent updates through
05–07 with its own auditable token.

## Stage commands

| Stage | Command |
|---|---|
| Capture | `gf capture`, `gf intake-update` |
| Triage | `gf triage` |
| Steward | `gf steward` |
| Review | `gf review` |
| Decide | `gf decide` |
| Propose | `gf propose` |
| Apply | `gf apply` |
| Quarantine | `gf quarantine` |
| Rollback | `gf rollback` |
