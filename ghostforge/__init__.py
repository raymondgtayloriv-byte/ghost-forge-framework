"""Ghost Forge Framework.

A review-gated memory/source-truth system for teams of AI agents.

Public re-implementation: the observer (Shadow Steward) collects evidence
read-only; the executor (Operator) moves material through review toward
canonical truth; canonical mutation is gated by an approval token. Model
output is draft material, never canonical truth by itself.
"""
from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["__version__"]
