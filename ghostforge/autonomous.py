"""Experimental autonomous promotion lane.

This module exists because the documented architecture contains a real
autonomous path ("exceptions-only review"). It is **experimental**,
**conservative**, **disabled by default**, and **dry-run by default**.

Gates (all must pass for a candidate to auto-promote):

* autonomous.enabled is true in config (default: false);
* the run is not a dry run only if autonomous.dry_run is false (default: true);
* candidate confidence >= autonomous.min_confidence;
* candidate has verified provenance (source hash matches the live file);
* source class is not in autonomous.excluded_source_classes — triage
  drafts, generated material, and unverified sources are NEVER
  auto-promoted;
* target directory is registered as a canonical target;
* nothing about the candidate is sensitive (sensitive notes never leave
  the machine and never auto-promote).

The lane never authors content: it promotes the candidate's verbatim
source content through the same gated apply path as human decisions. The
synthesized decision is marked decided_by="autonomous-lane" with its gate
evidence, so it is auditable and distinguishable from human approvals.

The approval token still gates the apply (proposal integrity), but in the
autonomous case it is *not* evidence of human review — provenance
(``decided_by`` carried through decision → proposal → canonical note and
manifest) is what distinguishes the two paths. Never treat a token as
proof of a human decision.
"""
from __future__ import annotations

import json
from pathlib import Path

from .vault import (
    lane, load_config, parse_note, sha256_file, today_str, utc_now,
    PathContainmentError, resolve_contained,
)
from .promotion import build_proposal, apply_proposal


def _autonomous_candidates(root: Path):
    review_dir = lane(root, "review_packets")
    cands = []
    for rp in sorted(review_dir.glob("*.md")):
        if rp.name == "_slate.md":
            continue
        fm, _ = parse_note(rp.read_text(encoding="utf-8"))
        if fm.get("status") != "awaiting-decision":
            continue
        cands.append((rp, fm))
    return cands


def evaluate(root: Path) -> dict:
    """Evaluate the autonomous lane without changing anything.

    Returns {"eligible": [...], "rejected": [(candidate_id, reason), ...]}.
    """
    root = Path(root)
    cfg = load_config(root)
    auto = cfg["autonomous"]
    eligible, rejected = [], []
    for rp, fm in _autonomous_candidates(root):
        cid = fm.get("candidate_id", rp.stem)
        src_rel = fm.get("source_path")
        try:
            src = resolve_contained(root, src_rel, purpose="autonomous source") if src_rel else None
        except PathContainmentError:
            rejected.append((cid, "source path escapes vault"))
            continue
        if not src or not src.exists():
            rejected.append((cid, "no live source to verify"))
            continue
        if sha256_file(src) != fm.get("source_hash"):
            rejected.append((cid, "source hash mismatch"))
            continue
        if fm.get("source_class") in auto["excluded_source_classes"]:
            rejected.append((cid, f"source class excluded: {fm.get('source_class')}"))
            continue
        conf = float(fm.get("confidence", 0) or 0)
        if conf < auto["min_confidence"]:
            rejected.append((cid, f"confidence {conf} < {auto['min_confidence']}"))
            continue
        if str(fm.get("sensitive", "false")).lower() != "false":
            rejected.append((cid, "sensitive material never auto-promotes"))
            continue
        eligible.append({"candidate_id": cid, "review_packet": str(rp),
                         "confidence": conf, "source_path": src_rel})
    return {"eligible": eligible, "rejected": rejected}


def run(root: Path, dry_run: bool = True) -> dict:
    """Run the autonomous lane. Refuses unless enabled in config.

    Even when enabled, a dry run changes nothing. Non-dry runs promote each
    eligible candidate's verbatim source content through the same gated
    apply path as human decisions.
    """
    root = Path(root)
    cfg = load_config(root)
    auto = cfg["autonomous"]
    if not auto["enabled"]:
        raise RuntimeError(
            "autonomous lane is disabled (autonomous.enabled=false). "
            "Enable it explicitly in 00_System/Config/ghostforge.json to use "
            "this experimental path."
        )
    if dry_run or auto["dry_run"]:
        result = evaluate(root)
        result["applied"] = []
        result["dry_run"] = True
        return result

    result = evaluate(root)
    applied = []
    for cand in result["eligible"]:
        rp = Path(cand["review_packet"])
        fm, _ = parse_note(rp.read_text(encoding="utf-8"))
        try:
            src = resolve_contained(root, fm["source_path"], purpose="autonomous source")
        except PathContainmentError:
            continue  # already gated in evaluate(); fail closed here too
        src_fm, src_body = parse_note(src.read_text(encoding="utf-8"))
        decision = {
            "decision_id": f"DEC-AUTO-{today_str()}-{cand['candidate_id'][:16]}",
            "candidate_id": cand["candidate_id"],
            "source_path": fm["source_path"],
            "source_hash": fm["source_hash"],
            "project": fm.get("project", "unassigned"),
            "action": "promote",
            "canonical_target": f"030 Projects/{fm.get('project', 'unassigned')}/Notes/",
            "title": str(src_fm.get("title") or src.stem),
            "body": src_body,
            "supersedes": None,
            "rationale": (
                f"autonomous lane: confidence {cand['confidence']}, "
                "hash-verified provenance, non-sensitive, registered target"
            ),
            "decided_by": "autonomous-lane",
            "decided_at": utc_now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        dpath = lane(root, "decisions") / f"{decision['decision_id']}.json"
        dpath.write_text(json.dumps(decision, indent=2), encoding="utf-8")
        proposal_path, token = build_proposal(root, dpath)
        run_id_ = apply_proposal(root, proposal_path, token)
        applied.append({"candidate_id": cand["candidate_id"],
                        "status": "promoted", "run_id": run_id_})
    result["applied"] = applied
    result["dry_run"] = False
    return result
