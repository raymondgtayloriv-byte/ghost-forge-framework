---
title: Harborlight beacon retry policy
canonical_truth: true
project: harborlight
promoted_from: 010 Inbox/Agent_Updates/2026-09-10/2026-09-10 1200 - harborlight -
  harborlight - harborlight-relay.md
source_hash: 8c901888e11e376f357e18c3ac7b1f1d7f1829d9d2bead96937df0c33d5e284a
promotion_run: GF-PROMOTE-20260910T164143Z
decision_id: DEC-2026-09-10-gf-steward-20260910t164142z-record-the-agreed-harborlight-beacon-retry-policy
decided_by: human
approved_by: human
supersedes: null
promoted_at: '2026-09-10T16:41:43Z'
---
Beacon retries are capped at three attempts with exponential backoff (1s/2s/4s). Validated in the relay simulator.
