# Agent Closeout Contract (current)

Every agent update is evidence, never canonical truth. The contract below
is what makes agent output machine-checkable. `gf intake-update` enforces it.

## 1. Location and filename

- Path: `010 Inbox/Agent_Updates/YYYY-MM-DD/`
- Filename: `YYYY-MM-DD HHMM - <project> - <lane> - <agent>.md`

## 2. Frontmatter (all required)

`action_id`, `project`, `lane`, `status`, `intent`, `agent`, `model`,
`effort`, `interface`, `date`, `effective_timestamp`, `sensitive`.

- `status`: one of `intake | complete | partial | blocked | failed | superseded`
- `sensitive`: `false`, or a class (`client-pii`, `credentials`,
  `private-business`, `internal-only`). Sensitive notes never leave the
  machine and never auto-promote.

## 3. Sections (in this order, none omitted)

1. Summary
2. Scope
3. Intent
4. Work completed
5. Not done / excluded
6. Validation
7. Truth / risk notes
8. Follow-up

An empty section says `None.` — it is never left blank, because "I didn't
write anything" and "there was nothing" must be distinguishable.

## 4. Signature (final line)

```
**Signed, <model display name> — <effort> — <interface> — <YYYY-MM-DD>**
```

This is authorship attestation, not cryptography. It says who ran, how
hard, through what interface, and when.

## 5. Append-only

Corrections are **new notes that supersede** the old one
(`status: superseded` on the old note, `supersedes:` on the new).
Historical notes are immutable and are never retrofitted.

## 6. Validation truth

The `Validation` section states what was actually checked — commands run,
tests passed, hashes verified. "Unverified" is a valid value; claiming
verification that did not happen is a contract violation.
