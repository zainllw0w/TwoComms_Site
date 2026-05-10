"""Phase 21 (2026-05-10) — review-related signal handlers.

Currently empty hook for IndexNow ping on first-approval transition;
will be filled in PR-4c when we wire the actual ``submit_indexnow``
service. Keeping the file here so ``apps.ReviewsConfig.ready()`` has
something to import.
"""
from __future__ import annotations
