"""Shared test-only cleanup for privacy-guarded Instagram analysis rows."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone


def purge_guarded_analysis_test_rows() -> dict:
    """Fence every guarded-row owner, commit, then use the production purge.

    ``TransactionTestCase`` uses SQL flush after ``tearDown``.  Production
    triggers correctly reject an unfenced DELETE, so migration-enabled tests
    must cross the same durable privacy boundary as runtime erasure.  This
    helper is deliberately test-only and never drops or disables a trigger.
    """
    from management.models import (
        IgAnalysisMaterialityEvent,
        IgAnalysisProposal,
        IgClient,
        IgConversationAnalysisEvent,
        IgConversationAnalysisResult,
        IgMemoryFact,
        IgMemoryHead,
    )

    guarded_models = (
        IgAnalysisMaterialityEvent,
        IgAnalysisProposal,
        IgConversationAnalysisEvent,
        IgConversationAnalysisResult,
        IgMemoryFact,
        IgMemoryHead,
    )
    client_ids = sorted({
        int(client_id)
        for model in guarded_models
        for client_id in model._base_manager.values_list("client_id", flat=True)
        if client_id
    })
    if not client_ids:
        return {"clients": 0, "rows": 0}

    fence_at = timezone.now()
    with transaction.atomic():
        locked_ids = list(
            IgClient.objects.select_for_update()
            .filter(pk__in=client_ids)
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        if locked_ids != client_ids:
            raise AssertionError(
                "privacy-guarded test rows have a missing client owner"
            )
        IgClient.objects.filter(pk__in=client_ids).update(
            privacy_erasure_started_at=fence_at,
            updated_at=fence_at,
        )

    from management.services.ig_typed_memory import purge_client_analysis_memory

    return purge_client_analysis_memory(client_ids)


class AnalysisPrivacyCleanupMixin:
    """TransactionTestCase mixin preserving strict production DELETE guards."""

    def tearDown(self):
        try:
            purge_guarded_analysis_test_rows()
        finally:
            super().tearDown()
