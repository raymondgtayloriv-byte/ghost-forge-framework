"""Promotion engine: the executor's gated path to canonical truth.

Pipeline stage order (nothing here is reachable without the earlier stages):

    review packet -> human decision JSON -> proposal (+ approval token)
    -> gated apply -> canonical note (+ manifest) ... or quarantine

Rules enforced by this module:

* Canonical mutation happens ONLY through :func:`apply_proposal`, and only
  with an approval token that verifies (HMAC over the exact proposal
  content). No bridge, triage output, packet, or scheduler artifact can
  bypass the token gate.
* Append-only: a canonical target path that already exists is refused
  unless the decision explicitly supersedes it (``supersedes`` field), in
  which case the old note keeps its content and the new note links back.
* Unknown/unavailable data is unsafe, never "zero": apply refuses when a
  source hash cannot be verified.
* Every apply writes a manifest (created files, hashes, decision id) so
  :func:`rollback` can undo it. Rollback removes created files; it never
  edits canonical content in place.
* Quarantine moves a candidate to ``070 Archive/Quarantine/`` with a reason;
  quarantined material is never auto-promoted.

Approval-token gating applies to canonical mutation/promotion. Intake,
status, review-packet, and proposal writes are explicitly non-token paths.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .vault import (
    lane, load_config, get_promotion_secret, parse_note, read_note, run_id,
    sha256_file, sha256_text, slugify, today_str, utc_now, write_note,
    PathContainmentError, resolve_contained,
)

DECISION_ACTIONS = {"promote", "quarantine", "defer"}


def _lane_child(root: Path, lane_name: str, filename: str) -> Path:
    """Resolve a lane-relative filename, contained under the lane directory.

    Lane filenames derive from review-packet, decision, or run ids — data
    that can be hand-edited — so they are contained, not merely joined.
    """
    try:
        return resolve_contained(lane(root, lane_name), filename, purpose=lane_name)
    except PathContainmentError as e:
        raise ValueError(str(e)) from e


# ---------------------------------------------------------------------------
# Decisions (human-authored)
# ---------------------------------------------------------------------------

def scaffold_decision(root: Path, candidate_id: str) -> Path:
    """Create a decision JSON scaffold for a review-packet candidate."""
    rp = _lane_child(root, "review_packets", f"{candidate_id}.md")
    if not rp.exists():
        raise FileNotFoundError(f"no review packet for candidate {candidate_id!r}")
    fm, _ = parse_note(rp.read_text(encoding="utf-8"))
    decision = {
        "decision_id": f"DEC-{today_str()}-{slugify(candidate_id)}",
        "candidate_id": candidate_id,
        "source_path": fm.get("source_path"),
        "source_hash": fm.get("source_hash"),
        "project": fm.get("project", "unassigned"),
        "action": "promote",  # or "quarantine" / "defer"
        "canonical_target": f"030 Projects/{fm.get('project', 'unassigned')}/Notes/",
        "title": "FILL ME: canonical note title",
        "body": "FILL ME: verified, compact canonical content",
        "supersedes": None,
        "rationale": "FILL ME: why this is safe to promote",
        "decided_by": "human",
        "decided_at": utc_now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "approval_token": None,  # filled by `gf propose`
    }
    dest = lane(root, "decisions") / f"{decision['decision_id']}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(decision, indent=2), encoding="utf-8")
    return dest


def load_decision(path: Path) -> dict:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    errors = []
    for key in ("decision_id", "candidate_id", "action", "decided_by"):
        if not d.get(key):
            errors.append(f"missing required key: {key}")
    if d.get("action") not in DECISION_ACTIONS:
        errors.append(f"action must be one of {sorted(DECISION_ACTIONS)}")
    if d.get("action") == "promote":
        for key in ("canonical_target", "title", "body", "rationale"):
            if not d.get(key) or str(d.get(key)).startswith("FILL ME"):
                errors.append(f"promote requires a completed '{key}'")
    if errors:
        raise ValueError("invalid decision:\n- " + "\n- ".join(errors))
    return d


# ---------------------------------------------------------------------------
# Proposals + approval tokens
# ---------------------------------------------------------------------------

def _canonical_proposal_dict(decision: dict) -> dict:
    """The exact content the token binds to."""
    return {
        "decision_id": decision["decision_id"],
        "candidate_id": decision["candidate_id"],
        "action": decision["action"],
        "canonical_target": decision.get("canonical_target"),
        "title": decision.get("title"),
        "body": decision.get("body"),
        "body_hash": sha256_text(decision.get("body") or ""),
        "source_path": decision.get("source_path"),
        "source_hash": decision.get("source_hash"),
        "project": decision.get("project", "unassigned"),
        "supersedes": decision.get("supersedes"),
        "rationale": decision.get("rationale"),
        "decided_by": decision.get("decided_by", "human"),
    }


def issue_token(secret: str, proposal: dict, ttl_hours: int = 72) -> str:
    """Issue an approval token bound to the exact proposal content."""
    payload = json.dumps(proposal, sort_keys=True)
    exp = (utc_now() + timedelta(hours=ttl_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    mac = hmac.new(secret.encode(), f"{exp}|{payload}".encode(), hashlib.sha256).hexdigest()
    return f"v1.{exp}.{mac}"


def verify_token(secret: str, token: str, proposal: dict) -> bool:
    try:
        version, exp, mac = token.split(".")
    except ValueError:
        return False
    if version != "v1":
        return False
    try:
        exp_dt = datetime.strptime(exp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    if exp_dt < utc_now():
        return False  # expired
    payload = json.dumps(proposal, sort_keys=True)
    expected = hmac.new(secret.encode(), f"{exp}|{payload}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, mac)


def build_proposal(root: Path, decision_path: Path) -> tuple[Path, str]:
    """Build a pending (non-canonical) proposal from a decision.

    Returns (proposal_path, approval_token). The token binds the proposal's
    exact content: it guarantees apply-time integrity, not the identity of
    the approver. In the human path, handing the token over models the
    explicit human handoff; in the autonomous path the token still protects
    apply semantics, but provenance (``decided_by``) is what distinguishes
    the two — never the token alone.
    """
    root = Path(root)
    cfg = load_config(root)
    secret = get_promotion_secret(cfg)
    decision = load_decision(decision_path)
    proposal = _canonical_proposal_dict(decision)
    token = issue_token(secret, proposal, cfg["promotion"]["token_ttl_hours"])
    pid = f"PROP-{decision['decision_id']}"
    pdir = _lane_child(root, "proposals", pid)
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "proposal.json").write_text(
        json.dumps(proposal, indent=2, sort_keys=True), encoding="utf-8"
    )
    write_note(
        pdir / "proposal.md",
        {"proposal_id": pid, "decision_id": decision["decision_id"],
         "action": decision["action"], "status": "pending-approval",
         "created": utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")},
        f"# Promotion proposal {pid}\n\n"
        f"Action: **{decision['action']}**\n\n"
        f"Target: `{decision.get('canonical_target')}`\n\n"
        "Status: pending — apply requires the approval token.\n",
    )
    return pdir / "proposal.json", token


def _resolve_canonical_target(root: Path, cfg: dict, target: str) -> Path:
    """Resolve a canonical target dir, contained under a registered root.

    The target must resolve underneath the vault root *and* underneath one
    of the configured canonical target roots. String-prefix matching is
    deliberately not used: ``..`` traversal, absolute paths, and symlink
    escapes are all rejected. Raises PermissionError on any violation.
    """
    try:
        tdir = resolve_contained(root, target, purpose="canonical target")
    except PathContainmentError as e:
        raise PermissionError(str(e)) from e
    for reg in cfg.get("canonical_targets", []):
        try:
            rroot = resolve_contained(root, reg, purpose="canonical target root")
        except PathContainmentError:
            continue
        if tdir == rroot or rroot in tdir.parents:
            return tdir
    raise PermissionError(f"target not registered as canonical: {target!r}")


def apply_proposal(root: Path, proposal_path: Path, token: str) -> str:
    """Gated canonical apply. Returns the promotion run id.

    Verifies the token, the source hash, target registration, and
    append-only constraints, then writes the canonical note + manifest.
    """
    root = Path(root)
    cfg = load_config(root)
    secret = get_promotion_secret(cfg)
    proposal = json.loads(Path(proposal_path).read_text(encoding="utf-8"))

    if not verify_token(secret, token, proposal):
        raise PermissionError("approval token invalid, expired, or mismatched: apply refused")

    if proposal["action"] == "quarantine":
        return _apply_quarantine(root, proposal)
    if proposal["action"] == "defer":
        raise ValueError("deferred proposals are not applied; they stay in the review queue")

    # --- promote path ---
    target_dir = proposal.get("canonical_target") or ""
    dest_dir = _resolve_canonical_target(root, cfg, target_dir)

    # Unknown/unavailable source data is unsafe, never "zero": the source
    # hash must verify against the live file. The source path itself must
    # resolve inside the vault — no absolute paths, no traversal, no
    # symlink escapes.
    src_rel = proposal.get("source_path")
    expected_hash = proposal.get("source_hash")
    if not src_rel or not expected_hash:
        raise ValueError("proposal lacks source provenance: apply refused")
    try:
        src = resolve_contained(root, src_rel, purpose="source path")
    except PathContainmentError as e:
        raise ValueError(str(e)) from e
    if not src.exists() or sha256_file(src) != expected_hash:
        raise ValueError("source hash mismatch or source missing: apply refused")

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{today_str()} - {slugify(proposal['title'])}.md"
    if dest.exists() and not proposal.get("supersedes"):
        raise FileExistsError(
            f"canonical target exists and decision does not supersede it: {dest}"
        )

    rid = run_id("GF-PROMOTE")
    ts = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    decided_by = proposal.get("decided_by", "human")
    fm = {
        "title": proposal["title"],
        "canonical_truth": True,
        "project": proposal.get("project", "unassigned"),
        "promoted_from": src_rel,
        "source_hash": expected_hash,
        "promotion_run": rid,
        "decision_id": proposal["decision_id"],
        "decided_by": decided_by,
        "approved_by": decided_by,
        "supersedes": proposal.get("supersedes"),
        "promoted_at": ts,
    }
    write_note(dest, fm, proposal["body"] or "")

    manifest = {
        "run_id": rid,
        "created": ts,
        "decision_id": proposal["decision_id"],
        "decided_by": decided_by,
        "created_files": [str(dest.relative_to(root))],
        "source": {"path": src_rel, "sha256": expected_hash},
    }
    mdir = lane(root, "promotions") / rid
    mdir.mkdir(parents=True, exist_ok=True)
    (mdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Mark the review packet decided.
    rp = _lane_child(root, "review_packets", f"{proposal['candidate_id']}.md")
    if rp.exists():
        fm_rp, body_rp = read_note(rp)
        fm_rp["status"] = "promoted"
        fm_rp["promotion_run"] = rid
        write_note(rp, fm_rp, body_rp)
    return rid


def _apply_quarantine(root: Path, proposal: dict) -> str:
    src_rel = proposal.get("source_path")
    if not src_rel:
        raise ValueError("quarantine requires a source path")
    try:
        src = resolve_contained(root, src_rel, purpose="quarantine source")
    except PathContainmentError as e:
        raise ValueError(str(e)) from e
    if not src.exists():
        raise ValueError("quarantine requires an existing source path")
    rid = run_id("GF-QUARANTINE")
    qdir = lane(root, "quarantine")
    qdir.mkdir(parents=True, exist_ok=True)
    original_text = src.read_text(encoding="utf-8")
    dest = qdir / f"{rid} - {src.name}"
    src.unlink()
    fm = {
        "quarantined_at": utc_now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reason": proposal.get("rationale") or "quarantined by human decision",
        "decision_id": proposal["decision_id"],
        "original_path": src_rel,
        "run_id": rid,
    }
    _, body = parse_note(original_text)
    write_note(dest, fm, body)
    return rid


def quarantine_candidate(root: Path, candidate_id: str, reason: str) -> Path:
    """Direct quarantine of a review candidate (human-initiated, no token needed)."""
    rp = _lane_child(root, "review_packets", f"{candidate_id}.md")
    if not rp.exists():
        raise FileNotFoundError(f"no review packet for candidate {candidate_id!r}")
    fm, body = read_note(rp)
    src_rel = fm.get("source_path")
    qdir = lane(root, "quarantine")
    qdir.mkdir(parents=True, exist_ok=True)
    rid = run_id("GF-QUARANTINE")
    if src_rel:
        try:
            src = resolve_contained(root, src_rel, purpose="quarantine source")
        except PathContainmentError as e:
            raise ValueError(str(e)) from e
        if src.exists():
            dest = qdir / f"{rid} - {src.name}"
            shutil.move(str(src), str(dest))
    fm["status"] = "quarantined"
    fm["quarantine_reason"] = reason
    fm["quarantined_at"] = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    out = qdir / f"{rid} - {slugify(candidate_id)}.md"
    return write_note(out, fm, body + f"\n\n**Quarantine reason:** {reason}\n")


def rollback(root: Path, run_id_: str) -> list[str]:
    """Undo a promotion run using its manifest. Returns removed paths."""
    manifest_path = _lane_child(root, "promotions", f"{run_id_}/manifest.json")
    if not manifest_path.exists():
        raise FileNotFoundError(f"no manifest for run {run_id_!r}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    removed = []
    for rel in manifest.get("created_files", []):
        try:
            p = resolve_contained(root, rel, purpose="manifest entry")
        except PathContainmentError as e:
            raise ValueError(str(e)) from e
        if p.exists():
            p.unlink()
            removed.append(rel)
    manifest["rolled_back_at"] = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return removed
