from django.db import migrations


CAPABILITIES = (
    ("operate_ig_bot", "Can operate Instagram bot"),
    (
        "view_ig_conversation_pii",
        "Can view Instagram conversation personal data",
    ),
    ("manage_ig_payments", "Can manage Instagram payment decisions"),
    ("edit_ig_prompt", "Can edit Instagram bot instructions"),
)
REVIEWER_GROUP_NAME = "Meta Bot Reviewer"


def create_permissions_and_preserve_existing_staff(apps, schema_editor):
    """Freeze pre-RBAC staff authority into explicit one-time grants."""
    alias = schema_editor.connection.alias
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    User = apps.get_model("auth", "User")
    AdminAuditLog = apps.get_model("management", "AdminAuditLog")

    content_type, _created = ContentType.objects.using(alias).get_or_create(
        app_label="management",
        model="instagrambotsettings",
    )
    permissions = []
    for codename, name in CAPABILITIES:
        permission, _created = Permission.objects.using(alias).get_or_create(
            content_type_id=content_type.pk,
            codename=codename,
            defaults={"name": name},
        )
        if permission.name != name:
            permission.name = name
            permission.save(update_fields=["name"], using=alias)
        permissions.append(permission)

    users = list(
        User.objects.using(alias)
        .filter(is_active=True, is_staff=True, is_superuser=False)
        .exclude(groups__name=REVIEWER_GROUP_NAME)
        .distinct()
    )
    assignments_added = 0
    for user in users:
        before = user.user_permissions.using(alias).filter(
            pk__in=[permission.pk for permission in permissions]
        ).count()
        user.user_permissions.add(*permissions)
        assignments_added += len(permissions) - before

    AdminAuditLog.objects.using(alias).create(
        actor=None,
        actor_role="migration",
        action="ig_bot.capabilities_staff_authority_preserved",
        entity_type="PermissionMigration",
        entity_id="active_nonreviewer_staff",
        before={"authority": "is_staff_or_is_superuser"},
        after={
            "target_count": len(users),
            "assignments_added": assignments_added,
            "capabilities": [codename for codename, _name in CAPABILITIES],
        },
        reason=(
            "One-time conversion of existing active non-superuser staff bot "
            "authority to explicit Django permissions; future staff are not granted."
        ),
        user_agent="",
    )


def preserve_later_grants_on_reverse(apps, schema_editor):
    """A reverse cannot distinguish migration grants from later approvals."""


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("management", "0190_ig_funnel_node_state"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="instagrambotsettings",
            options={
                "permissions": CAPABILITIES,
                "verbose_name": "Instagram bot settings",
                "verbose_name_plural": "Instagram bot settings",
            },
        ),
        migrations.RunPython(
            create_permissions_and_preserve_existing_staff,
            preserve_later_grants_on_reverse,
        ),
    ]
