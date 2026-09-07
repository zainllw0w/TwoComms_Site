import importlib
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from management.models import (
    AdminAuditLog,
    BotInstruction,
    BotPolicyPublication,
    InstagramBotSettings,
)
from management.bot_access import EDIT_IG_PROMPT_PERMISSION, META_REVIEWER_GROUP_NAME
from management.services.ig_policy_publication import (
    DraftRevisionConflict,
    PolicyPublicationError,
    PublicationHeadConflict,
    draft_state,
    load_active_policy_snapshot,
    publish_instruction_policy,
    rollback_instruction_policy,
    save_instruction_draft,
    select_policy_snapshot,
)


def _values(**overrides):
    values = {
        "title": "Sales guidance",
        "body": "Answer the customer using confirmed information.",
        "active": True,
        "priority": 100,
        "locale": "all",
        "tags": ["global"],
        "triggers": [],
        "programme_metadata": {},
        "allowed_actions": [],
        "trust_scope": "public_policy",
    }
    values.update(overrides)
    return values


class PolicyPublicationTests(TestCase):
    def setUp(self):
        BotInstruction.objects.all().delete()
        from management.tests_ig_policy_helpers import (
            ensure_test_instruction_publication,
        )

        ensure_test_instruction_publication()
        self.settings = InstagramBotSettings.load()
        self.actor = get_user_model().objects.create_user(
            username="policy-editor",
            password="unused-test-password",
        )

    def _head(self):
        self.settings.refresh_from_db()
        return self.settings.active_instruction_publication

    def _save(self, values=None, *, instruction_id=None, expected=None):
        self.settings.refresh_from_db()
        current = draft_state()
        return save_instruction_draft(
            expected_revision=(
                self.settings.instruction_draft_revision
                if expected is None else expected
            ),
            expected_snapshot_hash=current.snapshot_hash,
            instruction_id=instruction_id,
            values=values or _values(),
            actor=self.actor,
        )

    def _publish(self, state, *, head=None):
        head = self._head() if head is None else head
        return publish_instruction_policy(
            expected_draft_revision=state.revision,
            expected_draft_hash=state.snapshot_hash,
            expected_head_id=head.pk if head else None,
            expected_head_hash=head.snapshot_hash if head else "",
            actor=self.actor,
        )

    def test_draft_mutation_is_atomic_and_rejects_stale_revision(self):
        initial_revision = int(self.settings.instruction_draft_revision)
        instruction, state = self._save(expected=initial_revision)

        self.assertEqual(state.revision, initial_revision + 1)
        self.assertEqual(state.snapshot["instructions"][0]["source_id"], instruction.pk)
        with self.assertRaises(DraftRevisionConflict):
            self._save(
                values=_values(body="stale overwrite"),
                instruction_id=instruction.pk,
                expected=initial_revision,
            )
        instruction.refresh_from_db()
        self.assertNotEqual(instruction.body, "stale overwrite")
        self.assertTrue(AdminAuditLog.objects.filter(
            action="ig_bot.policy_draft_saved",
            entity_id=str(instruction.pk),
        ).exists())

    def test_publish_cas_moves_one_head_and_rejects_stale_head(self):
        _instruction, state = self._save()
        prior = self._head()
        result = self._publish(state, head=prior)

        self.assertTrue(result.changed)
        self.settings.refresh_from_db()
        self.assertEqual(
            self.settings.active_instruction_publication_id,
            result.publication.pk,
        )
        self.assertEqual(result.publication.parent_id, prior.pk)
        with self.assertRaises(PublicationHeadConflict):
            self._publish(state, head=prior)
        self.assertEqual(
            BotPolicyPublication.objects.filter(
                kind=BotPolicyPublication.Kind.PUBLISH
            ).count(),
            1,
        )

        same = self._publish(state, head=result.publication)
        self.assertFalse(same.changed)
        self.assertEqual(same.publication.pk, result.publication.pk)

    def test_rollback_restores_the_complete_metadata_snapshot(self):
        instruction, first_draft = self._save(_values(
            title="First",
            body="First body",
            priority=20,
            locale="uk",
            tags=["global", "programme:shooting_prize"],
            triggers=["size_question"],
            programme_metadata={
                "kind": "shooting_prize",
                "programme_id": "shooting_prize",
                "manager_required": True,
                "confirmed_visual_sample": False,
            },
            allowed_actions=["paylink"],
            trust_scope="public_policy",
        ))
        first = self._publish(first_draft).publication
        _same, second_draft = self._save(
            _values(
                title="Second",
                body="Second body",
                active=False,
                priority=900,
                locale="en",
                tags=["sales"],
                triggers=["price_question"],
                allowed_actions=["show_products"],
                trust_scope="operator_only",
            ),
            instruction_id=instruction.pk,
        )
        second = self._publish(second_draft, head=first).publication

        rollback = rollback_instruction_policy(
            target_publication_id=first.pk,
            expected_head_id=second.pk,
            expected_head_hash=second.snapshot_hash,
            actor=self.actor,
        ).publication

        self.assertEqual(rollback.kind, BotPolicyPublication.Kind.ROLLBACK)
        self.assertEqual(rollback.parent_id, second.pk)
        self.assertEqual(rollback.restored_from_id, first.pk)
        self.assertEqual(rollback.snapshot_hash, first.snapshot_hash)
        self.assertEqual(rollback.snapshot, first.snapshot)
        item = rollback.snapshot["instructions"][0]
        self.assertEqual(
            {
                "title": item["title"],
                "body": item["body"],
                "active": item["active"],
                "priority": item["priority"],
                "locale": item["locale"],
                "tags": item["tags"],
                "triggers": item["triggers"],
                "programme_metadata": item["programme_metadata"],
                "allowed_actions": item["allowed_actions"],
                "trust_scope": item["trust_scope"],
            },
            {
                "title": "First",
                "body": "First body",
                "active": True,
                "priority": 20,
                "locale": "uk",
                "tags": ["global", "programme:shooting_prize"],
                "triggers": ["size_question"],
                "programme_metadata": {
                    "kind": "shooting_prize",
                    "programme_id": "shooting_prize",
                    "manager_required": True,
                    "confirmed_visual_sample": False,
                },
                "allowed_actions": ["paylink"],
                "trust_scope": "public_policy",
            },
        )

    def test_public_preview_excludes_operator_only_without_disabling_checkout(self):
        public, state = self._save(_values(title="Public", body="Public body"))
        _private, state = self._save(
            _values(
                title="Private",
                body="Operator note must not reach the model.",
                allowed_actions=["manager"],
                trust_scope="operator_only",
            ),
            expected=state.revision,
        )

        preview = select_policy_snapshot(state.snapshot, public_only=True)

        self.assertEqual(preview["selected_ids"], [f"instruction:{public.pk}"])
        self.assertNotIn("Operator note", preview["rendered_text"])
        self.assertIn(
            {"id": f"instruction:{_private.pk}", "reason": "operator_only"},
            preview["omitted"],
        )
        self.assertIn("paylink", preview["effective_proposal_actions"])
        self.assertNotIn("manager", preview["declared_actions"])

    def test_sensitive_or_unimplemented_action_cannot_enter_draft(self):
        for action in ("paid", "refund", "discount_approval", "access_grant"):
            with self.subTest(action=action), self.assertRaises(
                PolicyPublicationError
            ) as caught:
                self._save(_values(allowed_actions=[action]))
            self.assertEqual(caught.exception.code, "unsupported_allowed_action")

    def test_live_selector_reads_bound_publication_not_newer_mutable_draft(self):
        from management.services.bot_playbooks import active_instruction_selection

        instruction, first_draft = self._save(_values(body="Published body"))
        publication = self._publish(first_draft).publication
        bound = load_active_policy_snapshot()
        _same, _newer_draft = self._save(
            _values(body="Unpublished mutable body"),
            instruction_id=instruction.pk,
        )

        selection = active_instruction_selection(publication_snapshot=bound)

        self.assertEqual(bound.publication_id, publication.pk)
        self.assertIn("Published body", selection.modules[0].body)
        self.assertNotIn("Unpublished mutable body", selection.modules[0].body)
        self.assertEqual(selection.publication_hash, publication.snapshot_hash)

    def test_programme_turns_off_only_after_whole_publication(self):
        from management.services.ig_prize_programme import (
            active_shooting_prize_programme,
        )

        instruction, first_draft = self._save(_values(
            title="Prize",
            body="Inspect the configured certificate.",
            tags=["programme:shooting_prize"],
            programme_metadata={
                "kind": "shooting_prize",
                "programme_id": "shooting_prize",
                "manager_required": True,
                "confirmed_visual_sample": False,
            },
        ))
        first = self._publish(first_draft).publication
        bound_first = load_active_policy_snapshot()
        programme = active_shooting_prize_programme(
            publication_snapshot=bound_first
        )
        self.assertIsNotNone(programme)
        self.assertEqual(len(programme.version), 64)

        _same, second_draft = self._save(
            _values(
                title="Prize",
                body="Inspect the configured certificate.",
                active=False,
                tags=["programme:shooting_prize"],
                programme_metadata={
                    "kind": "shooting_prize",
                    "programme_id": "shooting_prize",
                    "manager_required": True,
                    "confirmed_visual_sample": False,
                },
            ),
            instruction_id=instruction.pk,
        )
        self.assertIsNotNone(active_shooting_prize_programme(
            publication_snapshot=bound_first
        ))
        self._publish(second_draft, head=first)
        self.assertIsNone(active_shooting_prize_programme(
            publication_snapshot=load_active_policy_snapshot()
        ))

    def test_missing_active_pointer_is_explicit_readiness_failure(self):
        self.settings.active_instruction_publication = None
        self.settings.save(update_fields=["active_instruction_publication", "updated_at"])

        with self.assertRaises(PolicyPublicationError) as caught:
            load_active_policy_snapshot(self.settings)

        self.assertEqual(caught.exception.code, "active_publication_missing")


class PolicyBootstrapTests(SimpleTestCase):
    def test_bootstrap_preserves_only_reserved_shooting_programme(self):
        migration = importlib.import_module(
            "management.migrations.0196_bot_policy_publication"
        )
        row = SimpleNamespace(
            pk=17,
            title="Prize review",
            body="Inspect visible certificate cues.",
            intent_tags="global, on:delivery_question, programme:shooting_prize",
            is_active=True,
            priority=30,
        )

        item = migration._bootstrap_item(row)

        self.assertEqual(item["trust_scope"], "public_policy")
        self.assertEqual(item["triggers"], ["delivery_question"])
        self.assertEqual(item["allowed_actions"], [])
        self.assertEqual(item["programme_metadata"], {
            "kind": "shooting_prize",
            "programme_id": "shooting_prize",
            "manager_required": True,
            "confirmed_visual_sample": False,
        })


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class PolicyPublicationApiTests(TestCase):
    def setUp(self):
        BotInstruction.objects.all().delete()
        from management.tests_ig_policy_helpers import (
            ensure_test_instruction_publication,
        )

        ensure_test_instruction_publication()
        self.editor = get_user_model().objects.create_user(
            username="publication-api-editor",
            password="unused-test-password",
        )
        self.editor.user_permissions.add(Permission.objects.get(
            content_type__app_label="management",
            codename=EDIT_IG_PROMPT_PERMISSION.split(".", 1)[1],
        ))
        self.client.force_login(self.editor)

    def _state(self):
        response = self.client.get(reverse("management_bot_kb_api"))
        self.assertEqual(response.status_code, 200)
        return response.json()["policy"]

    def test_draft_preview_publish_conflict_history_and_rollback_api(self):
        initial = self._state()
        create = self.client.post(reverse("management_bot_kb_save_api"), {
            "type": "instruction",
            "title": "API instruction",
            "body": "Published through one whole snapshot.",
            "intent_tags": "global",
            "trigger_codes": "size_question",
            "priority": "25",
            "locale": "uk",
            "trust_scope": "public_policy",
            "allowed_actions": "show_products",
            "draft_revision": initial["draft_revision"],
            "draft_hash": initial["draft_hash"],
        })
        self.assertEqual(create.status_code, 200)
        draft = create.json()
        preview = self.client.post(reverse("management_bot_policy_preview_api"), {
            "draft_revision": draft["draft_revision"],
            "draft_hash": draft["draft_hash"],
            "locale": "uk",
            "audience_tags": "global",
            "turn_text": "Який розмір?",
        })
        self.assertEqual(preview.status_code, 200)
        self.assertTrue(preview.json()["ready"])
        self.assertEqual(len(preview.json()["selected"]), 1)

        head = initial["active_publication"]
        publish = self.client.post(reverse("management_bot_policy_publish_api"), {
            "draft_revision": draft["draft_revision"],
            "draft_hash": draft["draft_hash"],
            "head_id": head["id"],
            "head_hash": head["snapshot_hash"],
        })
        self.assertEqual(publish.status_code, 200)
        first = publish.json()["publication"]
        stale = self.client.post(reverse("management_bot_policy_publish_api"), {
            "draft_revision": draft["draft_revision"],
            "draft_hash": draft["draft_hash"],
            "head_id": head["id"],
            "head_hash": head["snapshot_hash"],
        })
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.json()["code"], "publication_head_conflict")

        current = self._state()
        instruction_id = create.json()["id"]
        update = self.client.post(reverse("management_bot_kb_save_api"), {
            "type": "instruction",
            "id": instruction_id,
            "title": "Changed title",
            "body": "Changed body.",
            "intent_tags": "sales",
            "trigger_codes": "price_question",
            "priority": "80",
            "locale": "en",
            "trust_scope": "operator_only",
            "draft_revision": current["draft_revision"],
            "draft_hash": current["draft_hash"],
        })
        current_head = current["active_publication"]
        second_publish = self.client.post(reverse("management_bot_policy_publish_api"), {
            "draft_revision": update.json()["draft_revision"],
            "draft_hash": update.json()["draft_hash"],
            "head_id": current_head["id"],
            "head_hash": current_head["snapshot_hash"],
        })
        second = second_publish.json()["publication"]
        rollback = self.client.post(reverse("management_bot_policy_rollback_api"), {
            "target_publication_id": first["id"],
            "head_id": second["id"],
            "head_hash": second["snapshot_hash"],
        })
        self.assertEqual(rollback.status_code, 200)
        self.assertEqual(
            rollback.json()["publication"]["restored_from_id"],
            first["id"],
        )
        history = self.client.get(reverse("management_bot_policy_history_api"))
        self.assertEqual(history.status_code, 200)
        self.assertGreaterEqual(len(history.json()["history"]), 4)
        self.assertNotIn("Published through", history.content.decode())

    def test_editor_ui_is_human_readable_and_reviewer_is_denied(self):
        page = self.client.get(reverse("management_bot"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Чернетка")
        self.assertContains(page, "Є неопубліковані зміни")
        self.assertContains(page, "Переглянути")
        self.assertContains(page, "Опублікувати")
        self.assertContains(page, "Історія")
        self.assertNotContains(page, "programme_metadata")

        reviewer = get_user_model().objects.create_superuser(
            username="publication-reviewer",
            password="unused-test-password",
        )
        reviewer.groups.add(Group.objects.get_or_create(
            name=META_REVIEWER_GROUP_NAME
        )[0])
        self.client.force_login(reviewer)
        for name in (
            "management_bot_policy_preview_api",
            "management_bot_policy_publish_api",
            "management_bot_policy_history_api",
            "management_bot_policy_rollback_api",
        ):
            response = (
                self.client.get(reverse(name))
                if name.endswith("history_api")
                else self.client.post(reverse(name), {})
            )
            self.assertEqual(response.status_code, 403)
