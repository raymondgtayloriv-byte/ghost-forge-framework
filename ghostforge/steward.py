"""Shadow Steward: the observer. Read-only collection, never promotion.

The steward walks the exact summarized-evidence roots (raw captures,
agent updates, triage digests), records hashes and provenance, and writes
timestamped evidence packets. Hard constraints, enforced by this module:

* no canonical writes — packets go to ``00_System/Packets/`` only;
* no automatic promotion — the steward cannot create proposals or apply them;
* raw markdown outside the evidence roots is ignored;
* visual assets are copied only into bounded review packets (see review.py);
  other attachments are recorded as metadata only;
* the archive is never read;
* no repository, network, or provider access — local files only.

The steward is deterministic, non-LLM collection logic. Two runs over
unchanged input collect the same evidence; packet files carry run
timestamps, so bytes may differ between runs.
"""
from __future__ import annotations

import json
from pathlib import Path

from .vault import (
    STEWARD_EVIDENCE_ROOTS, lane, parse_note, read_note, run_id, sha256_file,
    utc_now, write_note,
)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


def _evidence_files(root: Path):
    for lane_key in STEWARD_EVIDENCE_ROOTS:
        base = lane(root, lane_key)
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            if p.name.lower() == "readme.md":
                continue  # lane documentation, not evidence
            # Never read the archive, even if a root overlaps it (defense in depth).
            try:
                p.relative_to(lane(root, "archive"))
                continue
            except ValueError:
                pass
            yield lane_key, p


def collect(root: Path) -> Path:
    """Collect one evidence packet. Returns the packet directory.

    Read-only with respect to the vault: the only writes are the new packet
    files under ``00_System/Packets/<run-id>/``.
    """
    root = Path(root)
    rid = run_id("GF-STEWARD")
    ts = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    packet_dir = lane(root, "packets") / rid
    packet_dir.mkdir(parents=True, exist_ok=True)

    items: list[dict] = []
    for lane_key, p in _evidence_files(root):
        entry: dict = {
            "lane": lane_key,
            "path": str(p.relative_to(root)),
            "sha256": sha256_file(p),
            "bytes": p.stat().st_size,
        }
        if p.suffix.lower() == ".md":
            fm, _ = read_note(p)
            entry["frontmatter_keys"] = sorted(fm.keys())
            entry["project"] = str(fm.get("project", "unassigned"))
            entry["canonical_truth"] = bool(fm.get("canonical_truth", False))
            entry["source_class"] = str(fm.get("source_class", "unverified"))
        elif p.suffix.lower() in IMAGE_EXTS:
            # Visual assets are referenced, not embedded, at collection time.
            # Embedding happens only into bounded review packets (review.py).
            entry["kind"] = "image-asset"
            entry["note"] = "referenced only; copied into review packet on bridge"
        else:
            entry["kind"] = "attachment"
            entry["note"] = "recorded as metadata only"
        items.append(entry)

    manifest = {
        "run_id": rid,
        "created": ts,
        "observer": "shadow-steward",
        "canonical_writes": 0,
        "promotions": 0,
        "items": items,
    }
    (packet_dir / "packet.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )

    fm = {
        "run_id": rid,
        "created": ts,
        "type": "steward-packet",
        "canonical_truth": False,
        "items": len(items),
    }
    body = (
        f"# Steward evidence packet {rid}\n\n"
        f"Collected {len(items)} evidence items from the intake lanes. "
        "Read-only collection: no canonical writes, no promotions.\n\n"
        "See `packet.json` for hashes and provenance.\n"
    )
    write_note(packet_dir / "packet.md", fm, body)
    return packet_dir


def list_packets(root: Path) -> list[Path]:
    base = lane(root, "packets")
    if not base.exists():
        return []
    return sorted(p for p in base.iterdir() if p.is_dir())
