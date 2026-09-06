META_REVIEWER_GROUP_NAME = "Meta Bot Reviewer"

OPERATE_IG_BOT_PERMISSION = "management.operate_ig_bot"
VIEW_IG_CONVERSATION_PII_PERMISSION = "management.view_ig_conversation_pii"
MANAGE_IG_PAYMENTS_PERMISSION = "management.manage_ig_payments"
EDIT_IG_PROMPT_PERMISSION = "management.edit_ig_prompt"

BOT_CAPABILITY_PERMISSIONS = frozenset({
    OPERATE_IG_BOT_PERMISSION,
    VIEW_IG_CONVERSATION_PII_PERMISSION,
    MANAGE_IG_PAYMENTS_PERMISSION,
    EDIT_IG_PROMPT_PERMISSION,
})


def is_meta_bot_reviewer(user) -> bool:
    return bool(
        user.is_authenticated
        and user.groups.filter(name=META_REVIEWER_GROUP_NAME).exists()
    )


def _eligible_bot_principal(user) -> bool:
    if not (
        getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
    ):
        return False
    if is_meta_bot_reviewer(user):
        return False
    return True


def has_bot_capability(user, permission: str) -> bool:
    """Check one explicit bot capability with reviewer as a dominant deny."""
    if permission not in BOT_CAPABILITY_PERMISSIONS:
        return False
    if not _eligible_bot_principal(user):
        return False
    return bool(user.has_perm(permission))


def has_all_bot_capabilities(user, *permissions: str) -> bool:
    return bool(permissions) and set(permissions) <= BOT_CAPABILITY_PERMISSIONS and bool(
        _eligible_bot_principal(user)
        and all(user.has_perm(permission) for permission in permissions)
    )


def has_any_bot_capability(user) -> bool:
    return bool(
        _eligible_bot_principal(user)
        and any(user.has_perm(permission) for permission in BOT_CAPABILITY_PERMISSIONS)
    )
