"""Triage worker: deterministic, non-LLM classification of intake material.

Role in the architecture: the triage worker is the cheap first pass over
raw captures and agent updates. It extracts structure (links, tags,
headings, candidate entities), classifies each item into a lane, and emits
a *draft* triage note. Triage output is draft-only and is never canonical
truth; it is also explicitly excluded from autonomous promotion.

The shipped triage worker is deterministic rules-based logic (no model
calls), which makes it free, private, and reproducible. The
``LLMTriageAdapter`` interface documents where a cheap-model triager plugs
in: same input contract, same output contract, still draft-only.

Determinism note: two runs over unchanged input produce the same
classification decisions; output files carry timestamps, so bytes may
differ between runs.
"""
from __future__ import annotations

import re
from pathlib import Path

from .vault import (
    STEWARD_EVIDENCE_ROOTS, lane, parse_note, read_note, run_id, sha256_file,
    today_str, utc_now, write_note,
)

LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
TAG_RE = re.compile(r"(?<!\w)#([A-Za-z0-9_-]+)")
HEADING_RE = re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE)

# lane -> keywords (lowercase substring match against title+body)
LANE_RULES = [
    ("decision", ["decision", "decided", "approve", "chose", "selected"]),
    ("validation", ["test", "validated", "verified", "measured", "benchmark", "proof"]),
    ("incident", ["incident", "outage", "failure", "bug", "regression", "broken"]),
    ("build", ["implemented", "built", "shipped", "released", "deployed", "merged"]),
    ("research", ["investigated", "explored", "spike", "evaluated", "compared"]),
    ("operations", ["deployed", "backup", "scheduled", "monitored", "rotated"]),
]


def classify(title: str, body: str) -> tuple[str, float]:
    """Return (lane, confidence). Deterministic; ties resolve by rule order."""
    text = f"{title}\n{body}".lower()
    best_lane, best_hits = "general", 0
    for lane_name, keywords in LANE_RULES:
        hits = sum(1 for kw in keywords if kw in text)
        if hits > best_hits:
            best_lane, best_hits = lane_name, hits
    confidence = min(0.5 + 0.1 * best_hits, 0.95) if best_hits else 0.5
    return best_lane, round(confidence, 2)


def extract_entities(title: str, body: str) -> dict:
    text = f"{title}\n{body}"
    return {
        "links": sorted(set(LINK_RE.findall(text))),
        "tags": sorted(set(TAG_RE.findall(text))),
        "headings": HEADING_RE.findall(text)[:20],
    }


def triage_file(root: Path, path: Path) -> dict:
    """Triage one intake file. Pure function of the file's content.

    Paths are stored relative to the vault root so digests stay portable.
    """
    fm, body = read_note(path)
    title = str(fm.get("title") or fm.get("intent") or path.stem)
    lane_name, confidence = classify(title, body)
    entities = extract_entities(title, body)
    try:
        rel = str(path.relative_to(root))
    except ValueError:
        rel = str(path)
    return {
        "source_path": rel,
        "source_hash": sha256_file(path),
        "title": title,
        "project": str(fm.get("project", "unassigned")),
        "suggested_lane": lane_name,
        "confidence": confidence,
        "entities": entities,
        "source_class": "triage_draft",
        "canonical_truth": False,
    }


def _iter_evidence_files(root: Path):
    for lane_key in STEWARD_EVIDENCE_ROOTS:
        base = lane(root, lane_key)
        if not base.exists():
            continue
        for p in sorted(base.rglob("*.md")):
            if p.name.lower() == "readme.md":
                continue  # lane documentation, not evidence
            # Skip triage digests themselves to avoid feedback loops.
            if lane_key == "digests":
                continue
            yield p


def triage_inbox(root: Path) -> list[Path]:
    """Triage every intake file; write one draft digest per run.

    Returns the digest paths written. Idempotent in content: re-running over
    unchanged input reproduces the same classifications.
    """
    results = [triage_file(root, p) for p in _iter_evidence_files(root)]
    if not results:
        return []
    rid = run_id("GF-TRIAGE")
    ts = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    fm = {
        "run_id": rid,
        "created": ts,
        "type": "triage-digest",
        "canonical_truth": False,
        "source_class": "triage_draft",
        "items": len(results),
    }
    lines = [f"# Triage digest {rid}", ""]
    for r in results:
        lines.append(f"## {r['title']}")
        lines.append(f"- source: `{r['source_path']}`")
        lines.append(f"- source_hash: `{r['source_hash'][:12]}`")
        lines.append(f"- project: {r['project']}")
        lines.append(f"- suggested_lane: {r['suggested_lane']} (confidence {r['confidence']})")
        ents = r["entities"]
        if ents["links"]:
            lines.append(f"- links: {', '.join('[[' + l + ']]' for l in ents['links'])}")
        if ents["tags"]:
            lines.append(f"- tags: {', '.join('#' + t for t in ents['tags'])}")
        lines.append("")
    lines.append(
        "_Draft only. Triage output is not canonical truth and is excluded "
        "from autonomous promotion._"
    )
    dest = lane(root, "digests") / f"{today_str()}-triage-{rid}.md"
    return [write_note(dest, fm, "\n".join(lines) + "\n")]


class LLMTriageAdapter:
    """Documented seam for a cheap-model triage worker.

    A model-backed triager must accept the same input (intake file paths)
    and produce the same output contract as :func:`triage_file` — including
    ``canonical_truth: False`` and ``source_class: "triage_draft"`` — so
    that model output can never enter the canonical path directly. The
    shipped default is the deterministic worker above; this adapter is the
    integration point, not a second implementation.
    """

    def triage_file(self, root: Path, path: Path) -> dict:  # pragma: no cover - interface only
        raise NotImplementedError(
            "Plug a cheap-model triager here. It must return the triage_file() "
            "contract with canonical_truth=False."
        )
