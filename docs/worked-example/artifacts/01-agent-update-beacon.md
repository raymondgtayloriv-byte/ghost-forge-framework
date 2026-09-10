---
action_id: GF-HL-0001
project: harborlight
lane: harborlight
status: complete
intent: Record the agreed Harborlight beacon retry policy.
agent: harborlight-relay
model: Demo Model
effort: low
interface: cli
date: 2026-09-10
effective_timestamp: 2026-09-10T12:00:00+00:00
sensitive: false
---
## Summary
Beacon retries are capped at three attempts with exponential backoff (1s/2s/4s).

## Scope
Harborlight relay policy only.

## Intent
Record the agreed Harborlight beacon retry policy.

## Work completed
Validated the retry cap against the relay simulator.

## Not done / excluded
None.

## Validation
Simulator run passed: 3 attempts, backoff 1s/2s/4s.

## Truth / risk notes
Simulator is synthetic; production behavior unverified.

## Follow-up
None.

**Signed, Demo Model — low — cli — 2026-09-10**
