"""Intake: raw captures and Agent Updates.

Implements the public closeout contract (see
starter-vault/040 Agent Instructions/closeout-contract.md):

* Agent Updates land in ``010 Inbox/Agent_Updates/YYYY-MM-DD/`` with the
  filename ``YYYY-MM-DD HHMM - <project> - <lane> - <agent>.md``.
* Required frontmatter: action_id, project, lane, status, intent, agent,
  model, effort, interface, date, effective_timestamp, sensitive.
* Required sections, in order: Summary, Scope, Intent, Work completed,
  Not done / excluded, Validation, Truth / risk notes, Follow-up.
* Final line: ``**Signed, <model display name> — <effort> — <interface> — <YYYY-MM-DD>**``
  (authorship attestation, not cryptography).
* Append-only: corrections are new notes that supersede; never overwrite.

Agent Updates are evidence, never canonical truth by themselves.
"""
from __future__ import annotations

import re
from pathlib import Path

from .vault import lane, parse_note, slugify, today_str, write_note

REQUIRED_FM = [
    "action_id", "project", "lane", "status", "intent", "agent",
    "model", "effort", "interface", "date", "effective_timestamp", "sensitive",
]
REQUIRED_SECTIONS = [
    "Summary", "Scope", "Intent", "Work completed",
    "Not done / excluded", "Validation", "Truth / risk notes", "Follow-up",
]
VALID_STATUS = {"complete", "partial", "blocked", "failed", "intake", "superseded"}
VALID_SENSITIVE = {"false", "client-pii", "credentials", "private-business", "internal-only"}

FILENAME_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2}) (?P<time>\d{4}) - "
    r"(?P<project>.+?) - (?P<lane>.+?) - (?P<agent>.+?)\.md$"
)
SECTION_RE = re.compile(r"^## (.+?)\s*$", re.MULTILINE)
SIGNATURE_RE = re.compile(
    r"^\*\*Signed, .+ — .+ — .+ — \d{4}-\d{2}-\d{2}\*\*\s*$"
)

def validate_agent_update(text: str, filename: str = "") -> list[str]:
    """Return a list of contract violations (empty == valid)."""
    errors: list[str] = []
    fm, body = parse_note(text)

    if filename:
        m = FILENAME_RE.match(Path(filename).name)
        if not m:
            errors.append(
                "filename must match 'YYYY-MM-DD HHMM - <project> - <lane> - <agent>.md'"
            )
        elif str(fm.get("date")) != m.group("date"):
            errors.append("frontmatter 'date' must match the date in the filename")

    for key in REQUIRED_FM:
        if key not in fm or fm[key] in (None, ""):
            errors.append(f"missing required frontmatter key: {key}")

    if fm.get("status") not in VALID_STATUS:
        errors.append(f"status must be one of {sorted(VALID_STATUS)}")
    if str(fm.get("sensitive")).lower() not in VALID_SENSITIVE:
        errors.append(f"sensitive must be one of {sorted(VALID_SENSITIVE)}")

    sections = SECTION_RE.findall(body)
    if sections != REQUIRED_SECTIONS:
        errors.append(
            "sections must appear in order: " + ", ".join(REQUIRED_SECTIONS)
            + f" (found: {sections or 'none'})"
        )
    # No section may be omitted; an empty section says "None."
    for name in REQUIRED_SECTIONS:
        pattern = re.compile(
            r"^## " + re.escape(name) + r"\s*$\n(.*?)(?=^## |\Z)",
            re.MULTILINE | re.DOTALL,
        )
        m = pattern.search(body)
        if m and not m.group(1).strip():
            errors.append(f"section '{name}' is empty; write 'None.' instead of leaving it blank")

    lines = body.rstrip().splitlines()
    if not lines or not SIGNATURE_RE.match(lines[-1]):
        errors.append(
            "final line must be the signature: "
            "'**Signed, <model display name> — <effort> — <interface> — <YYYY-MM-DD>**'"
        )
    return errors


def intake_update(root: Path, src: Path) -> Path:
    """Validate an Agent Update draft and place it in the intake lane.

    Raises ValueError with the contract violations if invalid.
    Never overwrites: collisions get -2 / -3 suffixes.
    """
    text = Path(src).read_text(encoding="utf-8")
    errors = validate_agent_update(text, src.name)
    if errors:
        raise ValueError("Agent Update failed contract validation:\n- " + "\n- ".join(errors))
    fm, _ = parse_note(text)
    day = str(fm["date"])
    dest_dir = lane(root, "agent_updates") / day
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / Path(src).name
    n = 2
    while dest.exists():
        dest = dest_dir / f"{Path(src).stem}-{n}{Path(src).suffix}"
        n += 1
    dest.write_text(text, encoding="utf-8")
    return dest


def new_raw_capture(root: Path, project: str, title: str, body: str,
                    capture_type: str = "note") -> Path:
    """Write a raw capture note. Raw captures are unverified by definition."""
    ts = today_str()
    name = f"{ts} - {slugify(title)}.md"
    fm = {
        "title": title,
        "project": project,
        "capture_type": capture_type,
        "captured_at": ts,
        "canonical_truth": False,
        "status": "raw",
    }
    return write_note(lane(root, "raw_captures") / name, fm, body or "None.\n")


def new_agent_update_draft(root: Path, project: str, lane_name: str, agent: str,
                           action_id: str, intent: str) -> Path:
    """Scaffold a blank Agent Update draft satisfying the contract shape."""
    date = today_str()
    name = f"{date} 1200 - {project} - {lane_name} - {agent}.md"
    fm = {
        "action_id": action_id,
        "project": project,
        "lane": lane_name,
        "status": "intake",
        "intent": intent,
        "agent": agent,
        "model": "FILL ME",
        "effort": "FILL ME",
        "interface": "FILL ME",
        "date": date,
        "effective_timestamp": f"{date}T12:00:00+00:00",
        "sensitive": False,
    }
    body = "".join(f"## {s}\nNone.\n\n" for s in REQUIRED_SECTIONS)
    body += "**Signed, FILL ME — FILL ME — FILL ME — " + date + "**\n"
    dest = lane(root, "agent_raw_notes") / name
    return write_note(dest, fm, body)
