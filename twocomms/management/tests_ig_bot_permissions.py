import importlib
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse

from management.bot_access import (
    EDIT_IG_PROMPT_PERMISSION,
    MANAGE_IG_PAYMENTS_PERMISSION,
    META_REVIEWER_GROUP_NAME,
    OPERATE_IG_BOT_PERMISSION,
    VIEW_IG_CONVERSATION_PII_PERMISSION,
)
from management.models import AdminAuditLog, IgClient, InstagramBotSettings


@override_settings(
    ALLOWED_HOSTS=["management.twocomms.shop", "testserver"],
    ROOT_URLCONF="twocomms.urls_management",
    SECURE_SSL_REDIRECT=False,
)
class InstagramBotCapabilityTests(TestCase):
    host = "management.twocomms.shop"

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="capability-user", password="test-password"
        )
        self.staff = get_user_model().objects.create_user(
            username="new-generic-staff",
            password="test-password",
            is_staff=True,
        )
        self.client_record = IgClient.objects.create(igsid="880000001")

    def permission(self, dotted_name):
        app_label, codename = dotted_name.split(".", 1)
        return Permission.objects.get(
            content_type__app_label=app_label,
            codename=codename,
        )

    def grant(self, user, *permissions):
        user.user_permissions.add(*(self.permission(item) for item in permissions))
        return get_user_model().objects.get(pk=user.pk)

    def login(self, user):
        self.client.force_login(user)

    def get(self, name, *args):
        return self.client.get(
            reverse(name, args=args), HTTP_HOST=self.host, secure=True
        )

    def post(self, name, data=None, *args):
        return self.client.post(
            reverse(name, args=args),
            data or {},
            HTTP_HOST=self.host,
            secure=True,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_permissions_are_declared_on_the_settings_content_type(self):
        self.assertEqual(
            set(
                Permission.objects.filter(
                    content_type__app_label="management",
                    content_type__model="instagrambotsettings",
                    codename__in={
                        "operate_ig_bot",
                        "view_ig_conversation_pii",
                        "manage_ig_payments",
                        "edit_ig_prompt",
                    },
                ).values_list("codename", flat=True)
            ),
            {
                "operate_ig_bot",
                "view_ig_conversation_pii",
                "manage_ig_payments",
                "edit_ig_prompt",
            },
        )

    def test_migration_grants_existing_staff_once_and_never_reverses_later_grants(self):
        reviewer_staff = get_user_model().objects.create_user(
            username="reviewer-staff",
            password="test-password",
            is_staff=True,
        )
        reviewer_group = Group.objects.create(name=META_REVIEWER_GROUP_NAME)
        reviewer_staff.groups.add(reviewer_group)
        migration = importlib.import_module(
            "management.migrations.0191_instagram_bot_capabilities"
        )
        editor = SimpleNamespace(connection=connection)

        migration.create_permissions_and_preserve_existing_staff(apps, editor)

        self.staff.refresh_from_db()
        self.assertEqual(
            set(self.staff.user_permissions.values_list("codename", flat=True)),
            {
                "operate_ig_bot",
                "view_ig_conversation_pii",
                "manage_ig_payments",
                "edit_ig_prompt",
            },
        )
        self.assertFalse(reviewer_staff.user_permissions.exists())
        audit = AdminAuditLog.objects.get(
            action="ig_bot.capabilities_staff_authority_preserved"
        )
        self.assertEqual(audit.after["target_count"], 1)
        self.assertEqual(set(audit.after["capabilities"]), {
            "operate_ig_bot",
            "view_ig_conversation_pii",
            "manage_ig_payments",
            "edit_ig_prompt",
        })
        self.assertNotIn(self.staff.username, str(audit.after))

        migration.preserve_later_grants_on_reverse(apps, editor)
        self.assertEqual(self.staff.user_permissions.count(), 4)

    def test_new_staff_has_no_implicit_bot_access(self):
        self.login(self.staff)
        dashboard = self.get("management_bot")
        self.assertEqual(dashboard.status_code, 302)
        with patch("management.bot_views.bot.start_bot") as start_bot:
            response = self.post("management_bot_start_api")
        self.assertEqual(response.status_code, 403)
        start_bot.assert_not_called()

    def test_reviewer_is_dominant_deny_even_for_superuser_with_direct_permissions(self):
        reviewer = get_user_model().objects.create_superuser(
            username="reviewer-superuser", password="test-password"
        )
        reviewer.user_permissions.add(
            *(self.permission(item) for item in (
                OPERATE_IG_BOT_PERMISSION,
                VIEW_IG_CONVERSATION_PII_PERMISSION,
                MANAGE_IG_PAYMENTS_PERMISSION,
                EDIT_IG_PROMPT_PERMISSION,
            ))
        )
        group = Group.objects.create(name=META_REVIEWER_GROUP_NAME)
        reviewer.groups.add(group)
        self.login(reviewer)

        page = self.get("management_bot")
        self.assertEqual(page.status_code, 200)
        self.assertTemplateUsed(page, "management/bot_reviewer.html")
        self.assertNotContains(page, 'id="bot-start"')
        self.assertNotContains(page, 'name="system_prompt"')

        with patch("management.bot_views.bot.start_bot") as start_bot, patch(
            "management.bot_views.InstagramBotSettings.load"
        ) as load_settings:
            self.assertEqual(
                self.post("management_bot_start_api").status_code, 403
            )
            self.assertEqual(
                self.post(
                    "management_bot_settings_api", {"ai_enabled": "0"}
                ).status_code,
                403,
            )
        start_bot.assert_not_called()
        load_settings.assert_not_called()
        self.assertEqual(self.get("management_bot_clients_api").status_code, 403)

    def test_mixed_settings_submission_is_atomic(self):
        editor = self.grant(self.user, EDIT_IG_PROMPT_PERMISSION)
        self.login(editor)
        with patch("management.bot_views.InstagramBotSettings.load") as load_settings:
            response = self.post(
                "management_bot_settings_api",
                {"system_prompt": "new prompt", "ai_enabled": "0"},
            )
        self.assertEqual(response.status_code, 403)
        load_settings.assert_not_called()

    @override_settings(IG_BOT_POLICY_BUDGET_CHARS=1)
    def test_oversized_core_rejects_mixed_settings_before_any_mutation(self):
        editor_operator = self.grant(
            self.user,
            EDIT_IG_PROMPT_PERMISSION,
            OPERATE_IG_BOT_PERMISSION,
        )
        self.login(editor_operator)
        settings_row = InstagramBotSettings.load()
        settings_row.system_prompt = "existing prompt"
        settings_row.knowledge_base = "existing directives"
        settings_row.ai_enabled = True
        settings_row.save(
            update_fields=["system_prompt", "knowledge_base", "ai_enabled"]
        )

        response = self.post(
            "management_bot_settings_api",
            {
                "system_prompt": "replacement prompt",
                "knowledge_base": "replacement directives",
                "ai_enabled": "0",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.json()["code"])
        self.assertNotIn("replacement prompt", response.content.decode())
        settings_row.refresh_from_db()
        self.assertEqual(settings_row.system_prompt, "existing prompt")
        self.assertEqual(settings_row.knowledge_base, "existing directives")
        self.assertTrue(settings_row.ai_enabled)

    def test_operator_and_pii_permissions_are_both_required_for_client_action(self):
        operator = self.grant(self.user, OPERATE_IG_BOT_PERMISSION)
        self.login(operator)
        denied = self.post(
            "management_bot_client_hide_api", {}, self.client_record.pk
        )
        self.assertEqual(denied.status_code, 403)
        self.client_record.refresh_from_db()
        self.assertIsNone(self.client_record.hidden_at)

        operator = self.grant(operator, VIEW_IG_CONVERSATION_PII_PERMISSION)
        self.login(operator)
        allowed = self.post(
            "management_bot_client_hide_api", {}, self.client_record.pk
        )
        self.assertEqual(allowed.status_code, 200)
        self.client_record.refresh_from_db()
        self.assertIsNotNone(self.client_record.hidden_at)

    def test_payment_write_requires_payment_and_pii_permissions(self):
        payment_manager = self.grant(self.user, MANAGE_IG_PAYMENTS_PERMISSION)
        self.login(payment_manager)
        denied = self.post(
            "management_bot_payment_review_action_api", {}, 999999
        )
        self.assertEqual(denied.status_code, 403)

        payment_manager = self.grant(
            payment_manager, VIEW_IG_CONVERSATION_PII_PERMISSION
        )
        self.login(payment_manager)
        admitted = self.post(
            "management_bot_payment_review_action_api", {}, 999999
        )
        self.assertNotEqual(admitted.status_code, 403)

    def test_prompt_editor_can_edit_prompt_but_cannot_operate_or_view_clients(self):
        editor = self.grant(self.user, EDIT_IG_PROMPT_PERMISSION)
        self.login(editor)
        page = self.get("management_bot")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'name="system_prompt"')
        self.assertNotContains(page, 'id="bot-start"')
        self.assertNotContains(
            page,
            'class="bot-tab" role="tab" aria-selected="false" data-tab="clients"',
        )
        settings_row = InstagramBotSettings.load()
        response = self.post(
            "management_bot_settings_api", {"system_prompt": "bounded prompt"}
        )
        self.assertEqual(response.status_code, 200)
        settings_row.refresh_from_db()
        self.assertEqual(settings_row.system_prompt, "bounded prompt")
        self.assertEqual(self.get("management_bot_kb_api").status_code, 200)
        self.assertEqual(self.post("management_bot_start_api").status_code, 403)
        self.assertEqual(self.get("management_bot_clients_api").status_code, 403)

    def test_operator_without_pii_receives_allowlisted_status_without_logs(self):
        operator = self.grant(self.user, OPERATE_IG_BOT_PERMISSION)
        self.login(operator)
        marker = "private-status-marker"
        with patch(
            "management.bot_views.bot.status_snapshot",
            return_value={
                "state": "running",
                "running": True,
                "daemon_online": True,
                "pending": 2,
                "settings_revision": 7,
                "last_error": marker,
                "future_private": {"value": marker},
            },
        ):
            response = self.get("management_bot_status_api")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["log"], [])
        self.assertEqual(
            response.json()["status"],
            {
                "state": "running",
                "running": True,
                "daemon_online": True,
                "pending": 2,
                "settings_revision": 7,
            },
        )
        self.assertNotIn(marker, response.content.decode())

    def test_nonreviewer_superuser_retains_full_django_authority(self):
        supervisor = get_user_model().objects.create_superuser(
            username="bot-supervisor", password="test-password"
        )
        self.login(supervisor)
        with patch("management.bot_views.bot.start_bot") as start_bot:
            response = self.post("management_bot_start_api")
        self.assertEqual(response.status_code, 200)
        start_bot.assert_called_once_with()
        self.assertEqual(self.get("management_bot_clients_api").status_code, 200)
        self.assertEqual(self.get("management_bot_kb_api").status_code, 200)
