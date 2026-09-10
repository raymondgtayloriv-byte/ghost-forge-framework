# Roles

Roles are **model-agnostic**: they describe contracts, not which model
fills them. Bind whatever you run — frontier models, cheap models, local
models — to whichever role fits. The pipeline enforces the boundaries, so
a miscast role fails safe.

## Controller (human)

Owns the vault and the promotion secret. Writes decision JSONs, resolves
the exception queue, holds approval tokens. The only role whose judgment
can make something canonical.

## Bounded executor

Does scoped work and reports via signed agent updates (see
`040 Agent Instructions/closeout-contract.md`). Its output is evidence.
It cannot promote, and its notes are never canonical on arrival.

## Triage worker

Cheap first pass: classify, extract links/tags/headings, draft. Output is
draft-only and excluded from autonomous promotion. The shipped worker is
deterministic rules; `LLMTriageAdapter` documents where a cheap model plugs
in under the same output contract.

## Observer / Steward

Read-only collection over the evidence roots into timestamped packets.
Cannot write canonical notes, cannot propose, cannot promote. If the
observer is compromised or buggy, the worst it can do is write a bad
packet — the review bridge and the human still stand between it and truth.

## Operator

The pipeline runner and the only canonical writer — exclusively through
`gf apply` with a valid approval token. `tools/operator/` documents this
role's operational surface.

## Human approver

Reviews the approval slate; decides promote / quarantine / defer. In small
deployments this is the controller wearing a second hat; the pipeline
treats the hats as distinct steps regardless.

## Suggested bindings (examples, not requirements)

| Role | Example binding |
|---|---|
| Controller / approver | You |
| Bounded executor | Your strongest model, per task |
| Triage worker | A cheap local model, or the deterministic default |
| Observer | Deterministic collector (shipped) |
| Operator | Scheduler + `gf` CLI |

Swap any binding; the contracts don't move.
