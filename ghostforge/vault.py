"""Vault layout, frontmatter, hashing, config, and shared helpers.

Public re-implementation for ghost-forge-framework. All logic here is
authored fresh from the documented contracts; no private code is reused.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

# Canonical vault lanes (folder names are part of the method; the numbered
# prefixes encode lifecycle order: capture -> ... -> archive).
LANES = {
    "home": "000 Home",
    "system": "00_System",
    "config": "00_System/Config",
    "packets": "00_System/Packets",
    "proposals": "00_System/Proposals",
    "promotions": "00_System/Promotions",
    "inbox": "010 Inbox",
    "raw_captures": "010 Inbox/Raw Captures",
    "agent_raw_notes": "010 Inbox/Agent Raw Notes",
    "agent_updates": "010 Inbox/Agent_Updates",
    "digests": "010 Inbox/02_Digests",
    "review_packets": "010 Inbox/Review Packets",
    "exception_queue": "010 Inbox/Exception Queue",
    "decisions": "010 Inbox/Decisions",
    "daily": "020 Daily",
    "projects": "030 Projects",
    "agent_instructions": "040 Agent Instructions",
    "workflows": "050 Workflows",
    "references": "060 References",
    "templates": "060 References/Templates",
    "archive": "070 Archive",
    "quarantine": "070 Archive/Quarantine",
}

# Directories the Shadow Steward is allowed to collect from ("exact
# summarized-evidence roots"). Everything else is out of scope for collection.
STEWARD_EVIDENCE_ROOTS = ("raw_captures", "agent_updates", "digests")

DEFAULT_CONFIG = {
    "vault_name": "Ghost Forge Framework (starter)",
    "canonical_targets": ["030 Projects", "020 Daily"],
    "promotion": {
        # Name of the env var holding the promotion secret. The secret itself
        # is NEVER stored in the repo or the vault.
        "secret_env": "GHOST_FORGE_PROMOTION_SECRET",
        "token_ttl_hours": 72,
    },
    "autonomous": {
        "enabled": False,
        "dry_run": True,
        "min_confidence": 0.9,
        "require_provenance": True,
        # Source classes that may never auto-promote.
        "excluded_source_classes": ["triage_draft", "generated", "unverified"],
    },
}

CONFIG_FILENAME = "ghostforge.json"


# ---------------------------------------------------------------------------
# Paths / config
# ---------------------------------------------------------------------------

def lane(root: Path, name: str) -> Path:
    return Path(root) / LANES[name]


def load_config(root: Path) -> dict:
    cfg_path = lane(root, "config") / CONFIG_FILENAME
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy of defaults
    if cfg_path.exists():
        user = json.loads(cfg_path.read_text(encoding="utf-8"))
        _deep_merge(cfg, user)
    return cfg


def _deep_merge(base: dict, override: dict) -> None:
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def ensure_vault_skeleton(root: Path) -> None:
    """Create every lane directory. Never touches file contents."""
    root = Path(root)
    for d in LANES.values():
        (root / d).mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Path containment
# ---------------------------------------------------------------------------

class PathContainmentError(ValueError):
    """A vault-relative path escaped (or tried to escape) its allowed root."""


def resolve_contained(root: Path, rel: str | Path, *, purpose: str = "path") -> Path:
    """Resolve a vault-relative path, refusing anything that escapes ``root``.

    Rejects absolute paths outright, rejects ``..`` traversal that would
    leave ``root``, and resolves symlinks *before* checking containment so a
    symlink inside the vault cannot redirect an operation outside it.
    Returns the resolved absolute path. Ordinary nested paths are unaffected.
    """
    root_resolved = Path(root).resolve()
    rel_str = str(rel)
    if not rel_str or rel_str.strip() == "":
        raise PathContainmentError(f"{purpose}: empty path not allowed")
    p = Path(rel_str)
    if p.is_absolute():
        raise PathContainmentError(
            f"{purpose}: absolute paths not allowed: {rel_str!r}"
        )
    resolved = (root_resolved / p).resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise PathContainmentError(
            f"{purpose}: escapes its allowed root: {rel_str!r}"
        )
    return resolved


# ---------------------------------------------------------------------------
# Frontmatter notes
# ---------------------------------------------------------------------------

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def parse_note(text: str) -> tuple[dict, str]:
    """Split a Markdown note into (frontmatter dict, body str)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm = yaml.safe_load(m.group(1)) or {}
    return fm, text[m.end():]


def dump_note(fm: dict, body: str) -> str:
    """Serialize a note with YAML frontmatter."""
    if body and not body.endswith("\n"):
        body += "\n"
    return "---\n" + yaml.safe_dump(dict(fm), sort_keys=False).rstrip("\n") + "\n---\n" + body


def read_note(path: Path) -> tuple[dict, str]:
    return parse_note(Path(path).read_text(encoding="utf-8"))


def write_note(path: Path, fm: dict, body: str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_note(fm, body), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Hashing / ids / time
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def run_id(prefix: str = "GF-RUN") -> str:
    return f"{prefix}-{utc_now().strftime('%Y%m%dT%H%M%SZ')}"


def today_str() -> str:
    return utc_now().strftime("%Y-%m-%d")


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "untitled"


# ---------------------------------------------------------------------------
# Secrets handling
# ---------------------------------------------------------------------------

def get_promotion_secret(cfg: dict) -> str:
    """Read the promotion secret from its configured env var.

    Raises if unset: the engine refuses to issue or verify tokens without it.
    """
    env_name = cfg["promotion"]["secret_env"]
    secret = os.environ.get(env_name, "")
    if not secret:
        raise RuntimeError(
            f"Promotion secret not set: export {env_name} before issuing or "
            "applying promotions. The secret is never stored in the vault."
        )
    return secret
