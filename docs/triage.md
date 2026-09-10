# Triage

Triage is the pipeline's cheap first pass: it shrinks the review queue
without making truth judgments.

## The deterministic default

`ghostforge/triage.py` implements the shipped worker:

- **Input**: every Markdown file in the evidence roots
  (`010 Inbox/Raw Captures/`, `010 Inbox/Agent_Updates/`,
  `010 Inbox/02_Digests/`).
- **Extraction**: `[[links]]`, `#tags`, headings.
- **Classification**: keyword rules into lanes — decision, validation,
  incident, build, research, operations, general — with a classification
  confidence (not a truth confidence).
- **Output**: one draft digest per run in `010 Inbox/02_Digests/`, marked
  `canonical_truth: false`, `source_class: triage_draft`.

Two runs over unchanged input produce the same classifications. Output
files carry timestamps, so bytes may differ between runs — decisions are
deterministic, file bytes are not.

## Why deterministic first

- Free: no model calls, no API keys, no cost per run.
- Private: nothing leaves the machine.
- Reproducible: the same input classifies the same way, which makes the
  review bridge and tests honest.

## The cheap-model adapter

`ghostforge.triage.LLMTriageAdapter` is the documented seam for a
model-backed triager. The contract is strict on purpose:

- Same input: intake file paths.
- Same output: the `triage_file()` dict, including
  `canonical_truth: False` and `source_class: "triage_draft"`.

A model-backed triager that satisfies the contract gets model-quality
classification with pipeline-grade safety: its output still can't enter
the canonical path directly, and it's still excluded from autonomous
promotion.

## What triage never does

- Verify facts. Classification confidence ≠ truth confidence.
- Write canonical notes.
- Feed autonomous promotion. Triage drafts are excluded by source class,
  unconditionally.
