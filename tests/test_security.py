"""Tests: path containment — traversal, absolute paths, symlink escapes.

Every filesystem path that can derive from proposal, decision,
review-packet, config, or other vault-relative data must resolve inside
its allowed root. These are adversarial: each test attempts an escape and
asserts it is rejected.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ghostforge import promotion as promo_mod
from ghostforge import review as review_mod
from ghostforge import steward as steward_mod
from ghostforge import triage as triage_mod
from ghostforge.vault import (
    PathContainmentError,
    lane,
    parse_note,
    resolve_contained,
)


def _run_to_review(vault, filed_update):
    triage_mod.triage_inbox(vault)
    steward_mod.collect(vault)
    res = review_mod.bridge(vault)
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


def _retokened_proposal(vault, dpath, secret="test-secret-123", **overrides):
    """Build a proposal, then re-issue a valid token for a mutated copy.

    Mutation after issuance would invalidate the original token, so tests
    that need the *containment* gate (not the token gate) to fire must
    mint a fresh token for the mutated proposal — exactly what an attacker
    with the secret could do, and exactly what the containment layer must
    still refuse.
    """
    ppath, _token = promo_mod.build_proposal(vault, dpath)
    prop = json.loads(ppath.read_text(encoding="utf-8"))
    prop.update(overrides)
    token = promo_mod.issue_token(secret, prop)
    ppath.write_text(json.dumps(prop, indent=2, sort_keys=True), encoding="utf-8")
    return ppath, token


# --- primitive -------------------------------------------------------------

def test_resolve_contained_allows_normal_nested(vault):
    p = resolve_contained(vault, "030 Projects/harborlight/Notes/x.md")
    assert str(p).startswith(str(vault.resolve()))


def test_resolve_contained_rejects_dotdot_escape(vault):
    with pytest.raises(PathContainmentError):
        resolve_contained(vault, "030 Projects/../../outside.md")


def test_resolve_contained_rejects_absolute(vault):
    with pytest.raises(PathContainmentError):
        resolve_contained(vault, "/etc/passwd")


def test_resolve_contained_rejects_symlink_escape(vault, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("nope\n", encoding="utf-8")
    link = vault / "030 Projects" / "sneaky"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(PathContainmentError):
        resolve_contained(vault, "030 Projects/sneaky/secret.md")


def test_resolve_contained_allows_benign_dotdot(vault):
    # `..` that stays inside the root is fine — no weakening of valid paths.
    p = resolve_contained(vault, "030 Projects/../020 Daily/x.md")
    assert p == (vault.resolve() / "020 Daily" / "x.md")


# --- canonical targets -----------------------------------------------------

def test_apply_rejects_target_traversal(vault, filed_update):
    cid = _run_to_review(vault, filed_update)
    dpath = _completed_decision(vault, cid)
    ppath, token = _retokened_proposal(vault, dpath, canonical_target="030 Projects/../../pwned/")
    with pytest.raises(PermissionError):
        promo_mod.apply_proposal(vault, ppath, token)
    assert not (vault.parent / "pwned").exists()


def test_apply_rejects_target_prefix_sibling(vault, filed_update):
    # Old string-prefix matching would accept "030 ProjectsX/..." as under
    # "030 Projects". Real containment must not.
    (vault / "030 ProjectsX").mkdir(exist_ok=True)
    cid = _run_to_review(vault, filed_update)
    dpath = _completed_decision(vault, cid)
    ppath, token = _retokened_proposal(vault, dpath, canonical_target="030 ProjectsX/")
    with pytest.raises(PermissionError):
        promo_mod.apply_proposal(vault, ppath, token)


def test_apply_rejects_absolute_target(vault, filed_update, tmp_path):
    cid = _run_to_review(vault, filed_update)
    dpath = _completed_decision(vault, cid)
    ppath, token = _retokened_proposal(vault, dpath, canonical_target=str(tmp_path / "evil"))
    with pytest.raises(PermissionError):
        promo_mod.apply_proposal(vault, ppath, token)


def test_apply_rejects_symlink_target_escape(vault, filed_update, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = vault / "030 Projects" / "redir"
    link.symlink_to(outside, target_is_directory=True)
    cid = _run_to_review(vault, filed_update)
    dpath = _completed_decision(vault, cid)
    ppath, token = _retokened_proposal(vault, dpath, canonical_target="030 Projects/redir/")
    with pytest.raises(PermissionError):
        promo_mod.apply_proposal(vault, ppath, token)
    assert list(outside.glob("*.md")) == []


# --- source paths ----------------------------------------------------------

def test_apply_rejects_source_traversal(vault, filed_update):
    cid = _run_to_review(vault, filed_update)
    dpath = _completed_decision(vault, cid)
    ppath, token = _retokened_proposal(vault, dpath, source_path="../outside.md")
    with pytest.raises(ValueError):
        promo_mod.apply_proposal(vault, ppath, token)


def test_apply_rejects_absolute_source(vault, filed_update):
    cid = _run_to_review(vault, filed_update)
    dpath = _completed_decision(vault, cid)
    ppath, token = _retokened_proposal(vault, dpath, source_path="/etc/passwd")
    with pytest.raises(ValueError):
        promo_mod.apply_proposal(vault, ppath, token)


def test_apply_rejects_symlink_source_escape(vault, filed_update, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("hostile\n", encoding="utf-8")
    link = lane(vault, "raw_captures") / "link.md"
    link.symlink_to(outside)
    cid = _run_to_review(vault, filed_update)
    dpath = _completed_decision(vault, cid)
    ppath, token = _retokened_proposal(vault, dpath, source_path="010 Inbox/Raw Captures/link.md")
    with pytest.raises(ValueError):
        promo_mod.apply_proposal(vault, ppath, token)


# --- quarantine / rollback -------------------------------------------------

def test_quarantine_apply_rejects_traversal_source(vault, filed_update):
    cid = _run_to_review(vault, filed_update)
    dpath = promo_mod.scaffold_decision(vault, cid)
    d = json.loads(dpath.read_text(encoding="utf-8"))
    d.update({"action": "quarantine", "rationale": "test"})
    dpath.write_text(json.dumps(d, indent=2), encoding="utf-8")
    prop = promo_mod._canonical_proposal_dict(d)
    prop["source_path"] = "../../victim.md"
    (vault.parent / "victim.md").write_text("do not touch\n", encoding="utf-8")
    ppath = lane(vault, "proposals") / "PROP-TEST" / "proposal.json"
    ppath.parent.mkdir(parents=True, exist_ok=True)
    ppath.write_text(json.dumps(prop, indent=2, sort_keys=True), encoding="utf-8")
    token = promo_mod.issue_token("test-secret-123", prop)
    with pytest.raises(ValueError):
        promo_mod.apply_proposal(vault, ppath, token)
    assert (vault.parent / "victim.md").exists()  # untouched


def test_rollback_rejects_manifest_traversal(vault, filed_update):
    cid = _run_to_review(vault, filed_update)
    dpath = _completed_decision(vault, cid)
    ppath, token = promo_mod.build_proposal(vault, dpath)
    rid = promo_mod.apply_proposal(vault, ppath, token)
    mpath = lane(vault, "promotions") / rid / "manifest.json"
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    manifest["created_files"] = ["../../victim.md"]
    (vault.parent / "victim.md").write_text("do not touch\n", encoding="utf-8")
    mpath.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with pytest.raises(ValueError):
        promo_mod.rollback(vault, rid)
    assert (vault.parent / "victim.md").exists()  # untouched


def test_rollback_rejects_traversal_run_id(vault):
    with pytest.raises((ValueError, FileNotFoundError)):
        promo_mod.rollback(vault, "../../etc")


def test_scaffold_rejects_traversal_candidate(vault):
    with pytest.raises(ValueError):
        promo_mod.scaffold_decision(vault, "../../etc/passwd")


# --- review bridge ---------------------------------------------------------

def test_review_degrades_hostile_item_path(vault, filed_update):
    triage_mod.triage_inbox(vault)
    pdir = steward_mod.collect(vault)
    manifest_path = pdir / "packet.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["items"].append({
        "path": "../../etc/passwd", "sha256": "0" * 64, "project": "x",
    })
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    res = review_mod.bridge(vault)  # must not raise, must not read outside
    assert res["review_packets"] or res["exceptions"]
