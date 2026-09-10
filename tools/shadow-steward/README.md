# Shadow Steward — the observer

The Shadow Steward is the pipeline's **observer**: it sees everything in
the intake lanes and can change nothing canonical.

## Powers

- Walk the exact evidence roots: `010 Inbox/Raw Captures/`,
  `010 Inbox/Agent_Updates/`, `010 Inbox/02_Digests/`.
- Record SHA-256 hashes, sizes, frontmatter keys, and provenance per item.
- Write timestamped evidence packets to `00_System/Packets/<run-id>/`
  (`packet.json` + `packet.md`).

## Hard limits (enforced in `ghostforge/steward.py`)

- No canonical writes. The only writes are new packet files.
- No promotion, no proposals, no decisions.
- Raw material outside the evidence roots is ignored.
- The archive is never read.
- Visual assets are referenced at collection time; they are copied only
  into bounded review packets by the review bridge. Other attachments are
  metadata only.
- No network, no provider access, no repository access. Local files only.

## Determinism

Non-LLM, deterministic collection logic. Two runs over unchanged input
collect the same evidence; packet files carry run timestamps, so bytes
may differ between runs.

## Operation

```bash
gf steward --vault /path/to/vault   # collect one packet
gf status --vault /path/to/vault    # see packet count
```

The steward is the "S" in the observer/executor split: because it cannot
promote, a compromised or buggy observer can at worst write a bad packet —
the review bridge and the human gate still stand between it and truth.
