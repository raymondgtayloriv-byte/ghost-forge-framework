"""Shared pytest fixtures: a scratch vault with a starter skeleton."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from ghostforge import intake as intake_mod
from ghostforge.vault import ensure_vault_skeleton, lane

VALID_UPDATE = """---
action_id: GF-HL-0001
project: harborlight
lane: harborlight
status: complete
intent: Record the agreed Harborlight beacon retry policy.
agent: harborlight-triage
model: Demo Model
effort: low
interface: cli
date: {date}
effective_timestamp: {date}T12:00:00+00:00
sensitive: false
---

## Summary
Beacon retries are capped at three attempts with exponential backoff.

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

**Signed, Demo Model — low — cli — {date}**
"""


@pytest.fixture()
def vault(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    ensure_vault_skeleton(root)
    # Minimal config with a known secret env var.
    cfg_dir = lane(root, "config")
    (cfg_dir / "ghostforge.json").write_text(
        '{"vault_name": "test", "canonical_targets": ["030 Projects", "020 Daily"],'
        ' "promotion": {"secret_env": "GF_TEST_SECRET", "token_ttl_hours": 72},'
        ' "autonomous": {"enabled": false, "dry_run": true,'
        ' "min_confidence": 0.9, "require_provenance": true,'
        ' "excluded_source_classes": ["triage_draft", "generated", "unverified"]}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("GF_TEST_SECRET", "test-secret-123")
    return root


@pytest.fixture()
def update_file(tmp_path, vault):
    from ghostforge.vault import today_str
    date = today_str()
    p = tmp_path / "draft.md"
    p.write_text(VALID_UPDATE.format(date=date), encoding="utf-8")
    # The filename must satisfy the contract; rename accordingly.
    good = tmp_path / f"{date} 1200 - harborlight - harborlight - harborlight-triage.md"
    p.rename(good)
    return good


@pytest.fixture()
def filed_update(vault, update_file):
    return intake_mod.intake_update(vault, update_file)
