"""Audit and rollback for the hand-edited parts of the bot prompt.

Scope was chosen from measurement, not from the plan's wording. On production
``InstagramBotSettings.system_prompt`` is 3136 of ~26 900 assembled characters,
byte-identical to the constant in code, and was never saved through the form
(``settings_saved`` has zero log entries). Versioning it would produce empty
infrastructure over a field nobody touches.

What is genuinely edited through the interface and absent from git:
``BotInstruction`` bodies (7 rows) and the live ``knowledge_base``. Those are
what this module audits.
"""
from __future__ import annotations

from management.ig_bot_models import BotPromptRevision


def _actor_label(actor) -> str:
    if not actor:
        return ""
    return str(
        getattr(actor, "get_full_name", lambda: "")() or getattr(actor, "username", "")
    )[:150]


def record_instruction_revision(instruction, *, actor=None, previous_body="", note=""):
    """Record one edit of a bot instruction, or None when nothing changed."""
    if instruction is None or not getattr(instruction, "pk", None):
        return None
    body = str(instruction.body or "")
    previous = str(previous_body or "")
    if body == previous:
        # An empty revision is worse than none: it dilutes the history and makes
        # "who changed this" harder to answer, not easier.
        return None
    return BotPromptRevision.objects.create(
        target=BotPromptRevision.Target.INSTRUCTION,
        target_id=instruction.pk,
        kind=BotPromptRevision.Kind.EDIT,
        title=str(instruction.title or "")[:200],
        body=body,
        previous_body=previous,
        actor=actor if getattr(actor, "pk", None) else None,
        actor_label=_actor_label(actor),
        note=str(note or "")[:500],
    )


def record_knowledge_base_revision(settings_obj, *, actor=None, previous_body="", body=None, note=""):
    """Record one edit of the live operational directives block."""
    if settings_obj is None:
        return None
    new_body = str(
        settings_obj.knowledge_base if body is None else body
    )
    previous = str(previous_body or "")
    if new_body == previous:
        return None
    return BotPromptRevision.objects.create(
        target=BotPromptRevision.Target.KNOWLEDGE_BASE,
        target_id=settings_obj.pk,
        kind=BotPromptRevision.Kind.EDIT,
        title="knowledge_base",
        body=new_body,
        previous_body=previous,
        actor=actor if getattr(actor, "pk", None) else None,
        actor_label=_actor_label(actor),
        note=str(note or "")[:500],
    )


def rollback_revision(revision, *, actor=None):
    """Restore the body this revision replaced, and record the rollback itself.

    The rollback is a change like any other. Leaving it out of the history would
    make the log say the current text is the one from the last edit, which would
    be false.
    """
    if revision is None or not getattr(revision, "pk", None):
        return None
    restored = str(revision.previous_body or "")
    if revision.target == BotPromptRevision.Target.INSTRUCTION:
        from management.models import BotInstruction

        instruction = BotInstruction.objects.filter(pk=revision.target_id).first()
        if instruction is None:
            return None
        replaced = str(instruction.body or "")
        instruction.body = restored
        instruction.save(update_fields=["body", "updated_at"])
        title = str(instruction.title or "")[:200]
    else:
        from management.models import InstagramBotSettings

        settings_obj = InstagramBotSettings.load()
        replaced = str(settings_obj.knowledge_base or "")
        settings_obj.knowledge_base = restored
        settings_obj.save(update_fields=["knowledge_base"])
        title = "knowledge_base"
    return BotPromptRevision.objects.create(
        target=revision.target,
        target_id=revision.target_id,
        kind=BotPromptRevision.Kind.ROLLBACK,
        title=title,
        body=restored,
        previous_body=replaced,
        actor=actor if getattr(actor, "pk", None) else None,
        actor_label=_actor_label(actor),
        note=f"rollback of revision #{revision.pk}",
    )


def revision_history(*, target=None, target_id=None, limit=50) -> list[dict]:
    """Bounded, UI-ready history with a unified diff per row."""
    queryset = BotPromptRevision.objects.all()
    if target:
        queryset = queryset.filter(target=target)
    if target_id:
        queryset = queryset.filter(target_id=target_id)
    rows = []
    for revision in queryset.select_related("actor")[: max(1, min(int(limit), 200))]:
        rows.append({
            "id": revision.pk,
            "target": revision.target,
            "target_id": revision.target_id,
            "kind": revision.kind,
            "kind_label": revision.get_kind_display(),
            "title": revision.title,
            "actor": revision.actor_label or "автоматизація",
            "created_at": revision.created_at.isoformat(),
            "diff": revision.diff_lines()[:40],
            "note": revision.note,
        })
    return rows
