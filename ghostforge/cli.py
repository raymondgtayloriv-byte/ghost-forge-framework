"""`gf` — the Ghost Forge Framework command line.

Subcommands mirror the pipeline; every stage is explicit:

    gf init                  scaffold a starter vault
    gf capture               write a raw capture note
    gf intake-update          validate + file an Agent Update draft
    gf triage                deterministic triage pass over the inbox
    gf steward               observer: collect an evidence packet (read-only)
    gf review                bridge steward packets -> review packets + slate
    gf loop                  triage -> steward -> review (never canonical)
    gf decide                scaffold a human decision JSON for a candidate
    gf propose               build a pending proposal (+ approval token)
    gf apply                 gated canonical apply (needs the token)
    gf quarantine            quarantine a candidate with a reason
    gf rollback              undo a promotion run via its manifest
    gf auto-promote          experimental lane (disabled/dry-run by default)
    gf status                vault health overview

The vault is selected with --vault (default: ./vault) or GHOST_FORGE_VAULT.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from . import __version__
from . import autonomous as auto_mod
from . import intake as intake_mod
from . import promotion as promo_mod
from . import review as review_mod
from . import steward as steward_mod
from . import triage as triage_mod
from .vault import LANES, ensure_vault_skeleton, lane, load_config, read_note

REPO_ROOT = Path(__file__).resolve().parent.parent


def _vault(args) -> Path:
    v = Path(args.vault or os.environ.get("GHOST_FORGE_VAULT", "vault")).resolve()
    return v


def cmd_init(args):
    dest = _vault(args)
    if dest.exists() and any(dest.iterdir()) and not args.force:
        print(f"refusing: {dest} exists and is not empty (use --force)", file=sys.stderr)
        return 1
    src = REPO_ROOT / "starter-vault"
    if not src.exists():
        # Fall back to a bare skeleton when the bundled vault is absent.
        ensure_vault_skeleton(dest)
    else:
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
    ensure_vault_skeleton(dest)
    print(f"initialized starter vault at {dest}")
    return 0


def cmd_capture(args):
    root = _vault(args)
    body = Path(args.body_file).read_text(encoding="utf-8") if args.body_file else (args.body or "")
    p = intake_mod.new_raw_capture(root, args.project, args.title, body,
                                   capture_type=args.type)
    print(f"raw capture: {p.relative_to(root)}")
    return 0


def cmd_intake_update(args):
    root = _vault(args)
    try:
        p = intake_mod.intake_update(root, Path(args.file))
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(f"agent update filed: {p.relative_to(root)}")
    return 0


def cmd_triage(args):
    root = _vault(args)
    digests = triage_mod.triage_inbox(root)
    if not digests:
        print("nothing to triage")
    for d in digests:
        print(f"triage digest: {d.relative_to(root)}")
    return 0


def cmd_steward(args):
    root = _vault(args)
    pdir = steward_mod.collect(root)
    print(f"steward packet: {pdir.relative_to(root)} (read-only collection)")
    return 0


def cmd_review(args):
    root = _vault(args)
    res = review_mod.bridge(root)
    print(f"review packets: {len(res['review_packets'])}, "
          f"exceptions: {len(res['exceptions'])}")
    print(f"slate: {res['slate'].relative_to(root)}")
    return 0


def cmd_loop(args):
    root = _vault(args)
    triage_mod.triage_inbox(root)
    pdir = steward_mod.collect(root)
    res = review_mod.bridge(root)
    print(f"loop complete: packet {pdir.name}, "
          f"{len(res['review_packets'])} review packets, "
          f"{len(res['exceptions'])} exceptions (nothing canonical)")
    return 0


def cmd_decide(args):
    root = _vault(args)
    try:
        p = promo_mod.scaffold_decision(root, args.candidate)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(f"decision scaffold: {p.relative_to(root)}")
    print("Edit it (action, title, body, rationale), then run: gf propose --decision <file>")
    return 0


def cmd_propose(args):
    root = _vault(args)
    try:
        ppath, token = promo_mod.build_proposal(root, Path(args.decision))
    except (ValueError, RuntimeError) as e:
        print(str(e), file=sys.stderr)
        return 1
    print(f"proposal: {ppath.relative_to(root)}")
    print(f"APPROVAL TOKEN (present to gf apply): {token}")
    return 0


def cmd_apply(args):
    root = _vault(args)
    try:
        rid = promo_mod.apply_proposal(root, Path(args.proposal), args.token)
    except (PermissionError, ValueError, FileExistsError, RuntimeError) as e:
        print(f"apply refused: {e}", file=sys.stderr)
        return 1
    print(f"applied: {rid}")
    return 0


def cmd_quarantine(args):
    root = _vault(args)
    try:
        p = promo_mod.quarantine_candidate(root, args.candidate, args.reason)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(f"quarantined: {p.relative_to(root)}")
    return 0


def cmd_rollback(args):
    root = _vault(args)
    try:
        removed = promo_mod.rollback(root, args.run)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(f"rolled back {args.run}: removed {removed or 'nothing'}")
    return 0


def cmd_auto_promote(args):
    root = _vault(args)
    try:
        res = auto_mod.run(root, dry_run=not args.apply)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1
    mode = "APPLY" if args.apply else "dry-run"
    print(f"autonomous lane [{mode}]: {len(res['eligible'])} eligible, "
          f"{len(res['rejected'])} rejected")
    for cid, reason in res["rejected"]:
        print(f"  rejected {cid}: {reason}")
    for a in res["applied"]:
        print(f"  {a['status']}: {a['candidate_id']}")
    return 0


def cmd_status(args):
    root = _vault(args)
    cfg = load_config(root)
    counts = {}
    for key in ("agent_updates", "raw_captures", "digests", "review_packets",
                "exception_queue", "decisions", "proposals", "promotions", "quarantine"):
        base = lane(root, key)
        counts[key] = sum(1 for _ in base.rglob("*") if _.is_file()) if base.exists() else 0
    open_rp = 0
    rp_dir = lane(root, "review_packets")
    if rp_dir.exists():
        for rp in rp_dir.glob("*.md"):
            if rp.name == "_slate.md":
                continue
            fm, _ = read_note(rp)
            if fm.get("status") == "awaiting-decision":
                open_rp += 1
    packets = len(steward_mod.list_packets(root))
    print(f"ghost-forge-framework v{__version__} — vault: {root}")
    print(f"config: {cfg['vault_name']}; canonical targets: {cfg['canonical_targets']}")
    auto = cfg["autonomous"]
    print(f"autonomous lane: {'ENABLED (experimental)' if auto['enabled'] else 'disabled'}"
          f", dry_run={auto['dry_run']}")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    print(f"  steward packets: {packets}; open review candidates: {open_rp}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gf", description=__doc__)
    p.add_argument("--vault", default=None, help="vault directory (or GHOST_FORGE_VAULT)")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="scaffold a starter vault")
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("capture", help="write a raw capture note")
    s.add_argument("--project", required=True)
    s.add_argument("--title", required=True)
    s.add_argument("--body", default="")
    s.add_argument("--body-file", default=None)
    s.add_argument("--type", default="note")
    s.set_defaults(func=cmd_capture)

    s = sub.add_parser("intake-update", help="validate and file an Agent Update draft")
    s.add_argument("--file", required=True)
    s.set_defaults(func=cmd_intake_update)

    s = sub.add_parser("triage", help="deterministic triage pass over the inbox")
    s.set_defaults(func=cmd_triage)

    s = sub.add_parser("steward", help="observer: collect an evidence packet (read-only)")
    s.set_defaults(func=cmd_steward)

    s = sub.add_parser("review", help="bridge steward packets to review packets + slate")
    s.set_defaults(func=cmd_review)

    s = sub.add_parser("loop", help="triage -> steward -> review (never canonical)")
    s.set_defaults(func=cmd_loop)

    s = sub.add_parser("decide", help="scaffold a human decision JSON for a candidate")
    s.add_argument("--candidate", required=True)
    s.set_defaults(func=cmd_decide)

    s = sub.add_parser("propose", help="build a pending proposal (+ approval token)")
    s.add_argument("--decision", required=True)
    s.set_defaults(func=cmd_propose)

    s = sub.add_parser("apply", help="gated canonical apply (needs approval token)")
    s.add_argument("--proposal", required=True)
    s.add_argument("--token", required=True)
    s.set_defaults(func=cmd_apply)

    s = sub.add_parser("quarantine", help="quarantine a candidate with a reason")
    s.add_argument("--candidate", required=True)
    s.add_argument("--reason", required=True)
    s.set_defaults(func=cmd_quarantine)

    s = sub.add_parser("rollback", help="undo a promotion run via its manifest")
    s.add_argument("--run", required=True)
    s.set_defaults(func=cmd_rollback)

    s = sub.add_parser("auto-promote", help="experimental autonomous lane")
    s.add_argument("--apply", action="store_true",
                   help="actually promote (default is dry-run)")
    s.set_defaults(func=cmd_auto_promote)

    s = sub.add_parser("status", help="vault health overview")
    s.set_defaults(func=cmd_status)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
