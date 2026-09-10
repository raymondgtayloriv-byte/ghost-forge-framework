# Triage Rules (deterministic worker)

The triage worker is intentionally boring: deterministic, non-LLM,
free, private, reproducible. It exists to shrink the review queue, not to
make judgments.

## What it does

For each file in the evidence roots (`010 Inbox/Raw Captures/`,
`010 Inbox/Agent_Updates/`, `010 Inbox/02_Digests/`):

1. Extracts `[[links]]`, `#tags`, and headings.
2. Classifies into a lane by keyword rules (decision, validation,
   incident, build, research, operations, general).
3. Writes one draft digest per run to `010 Inbox/02_Digests/`.

## What it does not do

- It does not verify facts. Confidence here is classification
  confidence, not truth confidence.
- It does not write canonical notes.
- Its output is excluded from autonomous promotion (`source_class:
  triage_draft`).

## Determinism note

Two runs over unchanged input produce the same classifications. Output
files carry timestamps, so bytes may differ between runs.

## Cheap-model adapter

`ghostforge.triage.LLMTriageAdapter` documents the seam where a cheap
model plugs in: same input contract (intake file paths), same output
contract (`triage_file()` dict with `canonical_truth: False` and
`source_class: "triage_draft"`). A model-backed triager must satisfy the
same contract, so model output can never enter the canonical path directly.
