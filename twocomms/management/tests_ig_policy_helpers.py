"""Small publication helpers for tests that intentionally author draft rows."""
from django.db.models import Max

from management.models import (
    BotInstruction,
    BotPolicyPublication,
    InstagramBotSettings,
)
from management.services.ig_policy_publication import (
    PUBLICATION_COMPILER_VERSION,
    SNAPSHOT_SCHEMA_VERSION,
    draft_state,
    load_active_policy_snapshot,
    publish_instruction_policy,
    snapshot_from_rows,
    snapshot_hash,
)


def ensure_test_instruction_publication():
    """Create the migration-equivalent empty/current baseline when tests skip migrations."""
    settings_obj = InstagramBotSettings.load()
    if settings_obj.active_instruction_publication_id:
        return load_active_policy_snapshot(settings_obj=settings_obj)
    snapshot = snapshot_from_rows(
        BotInstruction.objects.all().order_by("priority", "id")
    )
    publication = BotPolicyPublication.objects.create(
        version=int(
            BotPolicyPublication.objects.aggregate(value=Max("version"))["value"] or 0
        ) + 1,
        kind=BotPolicyPublication.Kind.BOOTSTRAP,
        schema_version=SNAPSHOT_SCHEMA_VERSION,
        snapshot=snapshot,
        snapshot_hash=snapshot_hash(snapshot),
        compiler_version=PUBLICATION_COMPILER_VERSION,
        instruction_count=len(snapshot["instructions"]),
        actor_label="test-bootstrap",
        note="test fixture for migration-disabled settings",
    )
    settings_obj.active_instruction_publication = publication
    settings_obj.save(update_fields=["active_instruction_publication", "updated_at"])
    return load_active_policy_snapshot(settings_obj=settings_obj)


def publish_current_instructions():
    ensure_test_instruction_publication()
    state = draft_state()
    settings_obj = InstagramBotSettings.load()
    head = settings_obj.active_instruction_publication
    publish_instruction_policy(
        expected_draft_revision=state.revision,
        expected_draft_hash=state.snapshot_hash,
        expected_head_id=head.pk if head else None,
        expected_head_hash=head.snapshot_hash if head else "",
    )
    return load_active_policy_snapshot()
