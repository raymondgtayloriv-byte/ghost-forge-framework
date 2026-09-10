"""Tests: the gated promotion path — tokens, apply, rollback, quarantine."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ghostforge import autonomous as auto_mod
from ghostforge import promotion as promo_mod
from ghostforge import review as review_mod
from ghostforge import steward as steward_mod
from ghostforge import triage as triage_mod
from ghostforge.vault import lane, parse_note


def _run_to_review(vault, filed_update):
    triage_mod.triage_inbox(vault)
    steward_mod.collect(vault)
    res = review_mod.bridge(vault)
    # Return the candidate id for the agent update (not the triage digest).
    for rp in res["review_packets"]:
        fm, _ = parse_note(rp.read_text(encoding="utf-8"))
        if fm.get("source_class") == "agent-update":
            return fm["candidate_id"]
    raise AssertionError("no agent-update candidate bridged")


def _completed_decision(vault, candidate_id):
    dpath = promo_mod.scaffold_decision(vault, candidate_id)
    d = json.loads(dpath.read_text(encoding="utf-8"))
    d.update({
        "action": "promote",
        "title": "Harborlight beacon retry policy",
        "body": "Beacon retries are capped at three attempts with exponential backoff (1s/2s/4s).",
        "rationale": "Validated in the relay simulator; source hash verified.",
    })
    dpath.write_text(json.dumps(d, indent=2), encoding="utf-8")
    return dpath


def test_full_promote_path(vault, filed_update):
    cid = _run_to_review(vault, filed_update)
    dpath = _completed_decision(vault, cid)
    ppath, token = promo_mod.build_proposal(vault, dpath)
    assert token.startswith("v1.")
    rid = promo_mod.apply_proposal(vault, ppath, token)
    assert rid.startswith("GF-PROMOTE-")
    created = list((lane(vault, "projects") / "harborlight" / "Notes").glob("*.md"))
    assert len(created) == 1
    fm, _ = parse_note(created[0].read_text(encoding="utf-8"))
    assert fm["canonical_truth"] is True
    assert fm["approved_by"] == "human"


def test_apply_rejects_bad_token(vault, filed_update):
    cid = _run_to_review(vault, filed_update)
    dpath = _completed_decision(vault, cid)
    ppath, _token = promo_mod.build_proposal(vault, dpath)
    with pytest.raises(PermissionError):
        promo_mod.apply_proposal(vault, ppath, "v1.2099-01-01T00:00:00Z.deadbeef")


def test_apply_rejects_tampered_proposal(vault, filed_update):
    cid = _run_to_review(vault, filed_update)
    dpath = _completed_decision(vault, cid)
    ppath, token = promo_mod.build_proposal(vault, dpath)
    # Tamper after the token was issued: token must stop verifying.
    prop = json.loads(ppath.read_text(encoding="utf-8"))
    prop["body"] = "tampered content"
    ppath.write_text(json.dumps(prop, indent=2), encoding="utf-8")
    with pytest.raises(PermissionError):
        promo_mod.apply_proposal(vault, ppath, token)


def test_apply_rejects_unregistered_target(vault, filed_update):
    cid = _run_to_review(vault, filed_update)
    dpath = _completed_decision(vault, cid)
    d = json.loads(dpath.read_text(encoding="utf-8"))
    d["canonical_target"] = "070 Archive/Sneaky/"
    dpath.write_text(json.dumps(d, indent=2), encoding="utf-8")
    ppath, token = promo_mod.build_proposal(vault, dpath)
    with pytest.raises(PermissionError):
        promo_mod.apply_proposal(vault, ppath, token)


def test_apply_is_append_only(vault, filed_update):
    cid = _run_to_review(vault, filed_update)
    dpath = _completed_decision(vault, cid)
    ppath, token = promo_mod.build_proposal(vault, dpath)
    promo_mod.apply_proposal(vault, ppath, token)
    # Applying the same proposal again must refuse (target exists, no supersede).
    with pytest.raises(FileExistsError):
        promo_mod.apply_proposal(vault, ppath, token)


def test_rollback_undoes_apply(vault, filed_update):
    cid = _run_to_review(vault, filed_update)
    dpath = _completed_decision(vault, cid)
    ppath, token = promo_mod.build_proposal(vault, dpath)
    rid = promo_mod.apply_proposal(vault, ppath, token)
    removed = promo_mod.rollback(vault, rid)
    assert len(removed) == 1
    assert not list((lane(vault, "projects") / "harborlight" / "Notes").glob("*.md"))


def test_quarantine_path(vault, filed_update):
    cid = _run_to_review(vault, filed_update)
    q = promo_mod.quarantine_candidate(vault, cid, "needs human eyes first")
    assert "070 Archive/Quarantine" in str(q)
    fm, _ = parse_note(q.read_text(encoding="utf-8"))
    assert fm["status"] == "quarantined"


def test_autonomous_disabled_by_default(vault, filed_update):
    _run_to_review(vault, filed_update)
    with pytest.raises(RuntimeError):
        auto_mod.run(vault, dry_run=True)
    # evaluate() itself is safe to call and must exclude triage drafts.
    ev = auto_mod.evaluate(vault)
    assert all(e["candidate_id"] for e in ev["eligible"])
    for cid, _reason in ev["rejected"]:
        pass  # rejected list is informational


def test_autonomous_enabled_path_provenance(vault, filed_update, monkeypatch):
    """Enabled + non-dry-run autonomous run promotes with autonomous provenance.

    Also verifies the stricter eligibility boundary: a raw-capture rumor
    must be rejected, not promoted.
    """
    from ghostforge import intake as intake_mod
    from ghostforge.vault import read_note, today_str

    # Add an ineligible raw capture (unverified rumor) alongside the update.
    intake_mod.new_raw_capture(
        vault, "harborlight", "Rumor: north relay hardware fault",
        "Someone said the north relay hardware is failing. Unverified.",
    )
    cid = _run_to_review(vault, filed_update)
    cfg_path = lane(vault, "config") / "ghostforge.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["autonomous"]["enabled"] = True
    cfg["autonomous"]["dry_run"] = False
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

    res = auto_mod.run(vault, dry_run=False)
    assert res["dry_run"] is False
    assert len(res["applied"]) == 1
    assert res["applied"][0]["candidate_id"] == cid
    # The rumor must have been rejected by the eligibility gates.
    assert res["rejected"], "expected the raw-capture rumor to be rejected"

    created = list((lane(vault, "projects") / "harborlight" / "Notes").glob("*.md"))
    assert len(created) == 1
    fm, _ = read_note(created[0])
    assert fm["canonical_truth"] is True
    assert fm["decided_by"] == "autonomous-lane"
    assert fm["approved_by"] == "autonomous-lane"

    rid = res["applied"][0]["run_id"]
    manifest = json.loads(
        (lane(vault, "promotions") / rid / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["decided_by"] == "autonomous-lane"


def test_autonomous_dry_run_changes_nothing(vault, filed_update, monkeypatch):
    _run_to_review(vault, filed_update)
    cfg_path = lane(vault, "config") / "ghostforge.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["autonomous"]["enabled"] = True
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    before = {str(p) for p in Path(vault).rglob("*") if p.is_file()}
    res = auto_mod.run(vault, dry_run=True)
    after = {str(p) for p in Path(vault).rglob("*") if p.is_file()}
    assert res["dry_run"] is True
    assert after == before
