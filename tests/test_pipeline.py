"""Tests: intake contract, triage, steward read-only-ness."""
from __future__ import annotations

from pathlib import Path

import pytest

from ghostforge import intake as intake_mod
from ghostforge import review as review_mod
from ghostforge import steward as steward_mod
from ghostforge import triage as triage_mod
from ghostforge.vault import lane, read_note


def test_valid_update_passes(update_file):
    text = update_file.read_text(encoding="utf-8")
    assert intake_mod.validate_agent_update(text, update_file.name) == []


def test_invalid_update_fails(tmp_path):
    p = tmp_path / "bad.md"
    p.write_text("# no frontmatter, no sections\n", encoding="utf-8")
    errors = intake_mod.validate_agent_update(p.read_text(encoding="utf-8"), "bad.md")
    assert errors, "expected contract violations"
    assert any("filename" in e for e in errors)
    assert any("frontmatter" in e for e in errors)


def test_intake_places_file_in_dated_lane(vault, update_file, filed_update):
    assert filed_update.parent.name  # YYYY-MM-DD dir exists
    assert "010 Inbox" in str(filed_update)
    # Idempotent-ish: second intake of the same draft does not overwrite.
    second = intake_mod.intake_update(vault, update_file)
    assert second != filed_update
    assert second.exists()


def test_intake_rejects_invalid(vault, tmp_path):
    p = tmp_path / "bad.md"
    p.write_text("nope\n", encoding="utf-8")
    with pytest.raises(ValueError):
        intake_mod.intake_update(vault, p)


def test_triage_classifies_and_stays_draft(vault, filed_update):
    digests = triage_mod.triage_inbox(vault)
    assert len(digests) == 1
    fm, body = read_note(digests[0])
    assert fm["canonical_truth"] is False
    assert fm["source_class"] == "triage_draft"
    assert "suggested_lane" in body


def test_triage_deterministic(vault, filed_update):
    first = triage_mod.triage_inbox(vault)
    fm1, _ = read_note(first[0])
    # Wipe digests and re-run: same classifications.
    for p in lane(vault, "digests").glob("*.md"):
        p.unlink()
    second = triage_mod.triage_inbox(vault)
    fm2, body2 = read_note(second[0])
    assert fm1["items"] == fm2["items"]


def test_steward_is_read_only(vault, filed_update):
    before = {str(p) for p in Path(vault).rglob("*") if p.is_file()}
    pdir = steward_mod.collect(vault)
    after = {str(p) for p in Path(vault).rglob("*") if p.is_file()}
    new_files = after - before
    # The only new files are the packet files themselves.
    assert new_files and all(str(pdir) in f for f in new_files)
    manifest_fm, _ = read_note(pdir / "packet.md")
    assert manifest_fm["canonical_truth"] is False


def test_review_bridge_builds_packets_and_slate(vault, filed_update):
    triage_mod.triage_inbox(vault)
    steward_mod.collect(vault)
    res = review_mod.bridge(vault)
    assert len(res["review_packets"]) == 2  # the update + the triage digest... digest excluded? see below
    assert res["slate"].exists()


def test_review_bridge_idempotent(vault, filed_update):
    steward_mod.collect(vault)
    first = review_mod.bridge(vault)
    second = review_mod.bridge(vault)
    assert len(second["review_packets"]) == 0
    assert len(first["review_packets"]) >= 1
