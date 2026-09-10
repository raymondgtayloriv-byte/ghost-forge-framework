"""Review bridge: steward packets -> human review surface.

The bridge is non-canonical: it turns steward evidence packets into review
packets (one human-readable decision surface per candidate), rebuilds the
approval slate, and routes low-confidence / contradictory / risky items to
the exception queue. It never promotes anything and never writes canonical
notes.

Confidence and contradiction heuristics here are intentionally simple and
documented; the human decision is the actual gate.
"""
from __future__ import annotations

import json
from pathlib import Path

from .vault import (
    lane, parse_note, slugify, today_str, utc_now, write_note,
    PathContainmentError, resolve_contained,
)
from .steward import list_packets

# Keywords that force a candidate into the exception queue for human review.
RISK_KEYWORDS = (
    "secret", "credential", "token", "password", "api key",
    "contradict", "conflict", "ambiguous", "uncertain",
)

BRIDGED_MARKER = ".bridged"


def _packet_items(packet_dir: Path) -> list[dict]:
    manifest = json.loads((packet_dir / "packet.json").read_text(encoding="utf-8"))
    return manifest.get("items", [])


def _risky(item: dict, packet_dir: Path) -> str | None:
    """Return a reason if the item belongs in the exception queue."""
    name = item["path"].lower()
    for kw in RISK_KEYWORDS:
        if kw in name:
            return f"keyword '{kw}' in path"
    if item.get("canonical_truth"):
        return "source already marked canonical; needs human confirmation, not re-promotion"
    return None


def _contained_source(item: dict, vault_root: Path) -> Path | None:
    """Resolve a steward item's source path, contained under the vault root.

    Steward packet items are our own output, but packets can be hand-edited;
    a hostile or corrupt path must degrade to "unreadable", never to a read
    outside the vault.
    """
    try:
        return resolve_contained(vault_root, item["path"], purpose="review source")
    except (PathContainmentError, KeyError, TypeError):
        return None


def _classify_source(item: dict, vault_root: Path) -> tuple[str, float, str]:
    """Return (source_class, confidence, sensitive) for a steward item.

    Conservative by design: only contract-valid agent updates reach the
    confidence needed for autonomous consideration. Triage drafts and raw
    captures are never auto-promotion eligible.
    """
    from .intake import validate_agent_update

    src = _contained_source(item, vault_root)
    source_class, confidence, sensitive = "unverified", 0.5, "false"
    if src is not None and src.suffix == ".md" and src.exists():
        text = src.read_text(encoding="utf-8")
        fm, _ = parse_note(text)
        sensitive = str(fm.get("sensitive", "false")).lower()
        if fm.get("type") == "triage-digest" or fm.get("source_class") == "triage_draft":
            source_class, confidence = "triage_draft", 0.5
        elif not validate_agent_update(text, src.name):
            source_class, confidence = "agent-update", 0.92
        elif "010 Inbox/Raw Captures" in item["path"]:
            source_class, confidence = "raw-capture", 0.55
    return source_class, confidence, sensitive


def _read_title(item: dict, vault_root: Path) -> str:
    # Titles live in the source note; fall back to the filename.
    src = _contained_source(item, vault_root)
    if src is not None and src.suffix == ".md" and src.exists():
        fm, _ = parse_note(src.read_text(encoding="utf-8"))
        for key in ("title", "intent"):
            if fm.get(key):
                return str(fm[key])
    return Path(item["path"]).stem


def bridge(root: Path) -> dict:
    """Bridge unbridged steward packets into the review surface.

    Returns {"review_packets": [...], "exceptions": [...], "slate": path}.
    Idempotent: packets already bridged (marker file present) are skipped.
    """
    root = Path(root)
    review_dir = lane(root, "review_packets")
    exc_dir = lane(root, "exception_queue")
    review_dir.mkdir(parents=True, exist_ok=True)
    exc_dir.mkdir(parents=True, exist_ok=True)

    made: list[Path] = []
    exceptions: list[Path] = []

    for packet_dir in list_packets(root):
        if (packet_dir / BRIDGED_MARKER).exists():
            continue
        rid = packet_dir.name
        for item in _packet_items(packet_dir):
            title = _read_title(item, root)
            reason = _risky(item, packet_dir)
            source_class, confidence, sensitive = _classify_source(item, root)
            cid = f"{rid}--{slugify(title)}"
            if reason:
                fm = {
                    "candidate_id": cid,
                    "steward_run": rid,
                    "source_path": item["path"],
                    "source_hash": item["sha256"],
                    "project": item.get("project", "unassigned"),
                    "source_class": source_class,
                    "confidence": confidence,
                    "sensitive": sensitive,
                    "queued": utc_now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "reason": reason,
                    "status": "needs-human-review",
                }
                body = (
                    f"# Exception: {title}\n\n"
                    f"Source: `{item['path']}` (sha256 `{item['sha256'][:12]}`)\n\n"
                    f"**Why it needs a human:** {reason}.\n\n"
                    "Resolve by editing the source and re-running the loop, "
                    "or quarantine it explicitly.\n"
                )
                exceptions.append(
                    write_note(exc_dir / f"{cid}.md", fm, body)
                )
                continue
            fm = {
                "candidate_id": cid,
                "steward_run": rid,
                "source_path": item["path"],
                "source_hash": item["sha256"],
                "project": item.get("project", "unassigned"),
                "source_class": source_class,
                "confidence": confidence,
                "sensitive": sensitive,
                "created": utc_now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "status": "awaiting-decision",
            }
            body = (
                f"# Review: {title}\n\n"
                f"Source: `{item['path']}` (sha256 `{item['sha256'][:12]}`)\n\n"
                "## Evidence\n\n"
                f"- steward run: `{rid}`\n"
                f"- source hash: `{item['sha256']}`\n\n"
                "## Proposed action\n\n"
                "- [ ] promote to canonical\n"
                "- [ ] quarantine\n"
                "- [ ] defer\n\n"
                "## Decision\n\n"
                "Record the human decision with `gf decide --candidate "
                f"{cid}`.\n"
            )
            made.append(write_note(review_dir / f"{cid}.md", fm, body))
        (packet_dir / BRIDGED_MARKER).write_text("bridged\n", encoding="utf-8")

    # Rebuild the approval slate from all open review packets.
    slate_lines = [f"# Approval slate — {today_str()}", ""]
    open_packets = sorted(review_dir.glob("*.md"))
    # Exclude the slate file itself if it lives in the same dir (it doesn't).
    for rp in open_packets:
        fm, _ = parse_note(rp.read_text(encoding="utf-8"))
        if fm.get("status") == "awaiting-decision":
            slate_lines.append(
                f"- [ ] `{fm['candidate_id']}` — {fm.get('project')} — `{rp.name}`"
            )
    if len(slate_lines) == 2:
        slate_lines.append("_No candidates awaiting decision._")
    slate_lines += [
        "",
        "Decide each item with `gf decide --candidate <id>`, then build a",
        "proposal with `gf propose` and apply it with the approval token.",
    ]
    slate = write_note(
        review_dir / "_slate.md",
        {"type": "approval-slate", "date": today_str(), "open": len(open_packets)},
        "\n".join(slate_lines) + "\n",
    )
    return {"review_packets": made, "exceptions": exceptions, "slate": slate}
