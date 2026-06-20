"""Блок B: політики мереж у пайплайні чекера (skip/apply/recheck + навчання)."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from management.models import (
    LeadAICheck,
    LeadCheckJob,
    LeadNetwork,
    NetworkAlias,
    ManagementLead,
)
from management.services import lead_check_job as ljob
from management.services import lead_checker
from management.services import network_policy

User = get_user_model()


def _lead(name="Shop", phone=None, **kw):
    phone = phone or ("050" + str(1000000 + ManagementLead.objects.count()))
    defaults = dict(shop_name=name, phone=phone, lead_source=ManagementLead.LeadSource.PARSER)
    defaults.update(kw)
    return ManagementLead.objects.create(**defaults)


def _confirmed_network(policy, **kw):
    admin = User.objects.create(username="admin" + str(User.objects.count()))
    return LeadNetwork.objects.create(
        canonical_name=kw.pop("canonical_name", "Net"),
        slug=kw.pop("slug", "net" + str(LeadNetwork.objects.count())),
        policy=policy, confirmed_by=admin, **kw,
    )


class ResolveDecisionTests(TestCase):
    def test_no_network_is_full_ai(self):
        lead = _lead()
        self.assertEqual(network_policy.resolve_decision(lead).action, "full_ai")

    def test_unconfirmed_network_is_full_ai(self):
        # навіть з block-політикою непідтверджена мережа НЕ впливає
        net = LeadNetwork.objects.create(
            canonical_name="X", slug="x", policy=LeadNetwork.Policy.BLOCK_NO_COLLAB,
        )
        lead = _lead(network=net)
        self.assertEqual(network_policy.resolve_decision(lead).action, "full_ai")

    def test_confirmed_block_is_skip_unfit(self):
        net = _confirmed_network(LeadNetwork.Policy.BLOCK_NO_COLLAB)
        lead = _lead(network=net)
        d = network_policy.resolve_decision(lead)
        self.assertEqual(d.action, "skip_block")
        self.assertEqual(d.verdict_band, "unfit")
        self.assertTrue(d.is_skip)

    def test_confirmed_apply_known_uses_policy_params_band(self):
        net = _confirmed_network(
            LeadNetwork.Policy.APPLY_KNOWN_VERDICT, policy_params={"known_verdict_band": "fit"},
        )
        lead = _lead(network=net)
        d = network_policy.resolve_decision(lead)
        self.assertEqual(d.action, "apply_known")
        self.assertEqual(d.verdict_band, "fit")

    def test_confirmed_recheck_threads_instructions(self):
        net = _confirmed_network(
            LeadNetwork.Policy.RECHECK_EACH, extra_instructions="Перевір лише наявність текстилю",
        )
        lead = _lead(network=net)
        d = network_policy.resolve_decision(lead)
        self.assertEqual(d.action, "recheck_with_instructions")
        self.assertIn("текстилю", d.extra_instructions)
        self.assertFalse(d.is_skip)

    def test_confirmed_priority_target_is_full_ai(self):
        net = _confirmed_network(LeadNetwork.Policy.PRIORITY_TARGET)
        lead = _lead(network=net)
        self.assertEqual(network_policy.resolve_decision(lead).action, "full_ai")


class ApplyDecisionTests(TestCase):
    def test_skip_creates_done_check_without_tokens(self):
        net = _confirmed_network(LeadNetwork.Policy.BLOCK_NO_COLLAB)
        lead = _lead(network=net)
        decision = network_policy.resolve_decision(lead)
        check = network_policy.apply_decision(lead, decision)
        self.assertEqual(check.status, LeadAICheck.Status.DONE)
        self.assertEqual(check.verdict_band, "unfit")
        self.assertEqual(check.tokens, {})
        self.assertTrue(check.model_used.startswith("(policy:"))
        lead.refresh_from_db()
        self.assertEqual(lead.ai_verdict, "unfit")
        self.assertEqual(lead.niche_status, ManagementLead.NicheStatus.NON_NICHE)
        net.refresh_from_db()
        self.assertEqual(net.skipped_count, 1)
        self.assertEqual(net.tokens_saved, network_policy.ESTIMATED_TOKENS_PER_FULL_CHECK)


class LearnNetworkFromCheckTests(TestCase):
    def _check(self, lead, **signals):
        return LeadAICheck.objects.create(
            lead=lead, status=LeadAICheck.Status.DONE, signals=signals,
            brand_summary="Мережа спортивного одягу",
        )

    def test_creates_ai_suggested_network(self):
        lead = _lead()
        check = self._check(
            lead, canonical_network_name="MultiFit",
            suggested_policy="recheck_each", network_kind="chain_brand",
        )
        net = network_policy.learn_network_from_check(lead, check)
        self.assertIsNotNone(net)
        self.assertTrue(net.suggested_by_ai)
        self.assertEqual(net.policy, LeadNetwork.Policy.RECHECK_EACH)
        self.assertEqual(net.kind, LeadNetwork.Kind.CHAIN_BRAND)
        lead.refresh_from_db()
        self.assertEqual(lead.network_id, net.id)
        self.assertEqual(lead.network_membership_source, "ai")

    def test_empty_signal_is_noop(self):
        lead = _lead()
        check = self._check(lead, canonical_network_name="")
        self.assertIsNone(network_policy.learn_network_from_check(lead, check))
        self.assertEqual(LeadNetwork.objects.count(), 0)

    def test_does_not_override_confirmed_network(self):
        net = _confirmed_network(LeadNetwork.Policy.PRIORITY_TARGET, canonical_name="Confirmed")
        lead = _lead(network=net, network_membership_source="manual")
        check = self._check(lead, canonical_network_name="SomethingElse", suggested_policy="block_no_collab")
        result = network_policy.learn_network_from_check(lead, check)
        self.assertEqual(result.id, net.id)
        lead.refresh_from_db()
        self.assertEqual(lead.network_id, net.id)
        self.assertEqual(LeadNetwork.objects.count(), 1)

    def test_idempotent_reuses_name_alias(self):
        lead1 = _lead(name="FitOne")
        lead2 = _lead(name="FitTwo")
        c1 = self._check(lead1, canonical_network_name="GymBrand")
        c2 = self._check(lead2, canonical_network_name="GymBrand")
        n1 = network_policy.learn_network_from_check(lead1, c1)
        n2 = network_policy.learn_network_from_check(lead2, c2)
        self.assertEqual(n1.id, n2.id)
        self.assertEqual(LeadNetwork.objects.count(), 1)


class PromptInstructionsTests(TestCase):
    def test_extra_instructions_block_present(self):
        prompt = lead_checker.build_system_prompt("ОСОБЛИВЕ ПРАВИЛО ABC")
        self.assertIn("ДОДАТКОВІ ВКАЗІВКИ", prompt)
        self.assertIn("ОСОБЛИВЕ ПРАВИЛО ABC", prompt)

    def test_no_extra_instructions_no_block(self):
        self.assertNotIn("ДОДАТКОВІ ВКАЗІВКИ", lead_checker.build_system_prompt(""))


class RunStepPipelineTests(TestCase):
    def _job(self, **kw):
        defaults = dict(status=LeadCheckJob.Status.RUNNING, scope="all", total_selected=1)
        defaults.update(kw)
        return LeadCheckJob.objects.create(**defaults)

    def test_run_step_skips_confirmed_block_without_ai(self):
        net = _confirmed_network(LeadNetwork.Policy.BLOCK_IRRELEVANT)
        lead = _lead(network=net)
        job = self._job()
        with patch.object(lead_checker, "score_lead") as score_mock:
            ljob.run_step(job)
            score_mock.assert_not_called()
        lead.refresh_from_db()
        net.refresh_from_db()
        self.assertEqual(lead.ai_verdict, "unfit")
        self.assertEqual(job.processed, 1)
        self.assertEqual(job.scored, 1)
        self.assertEqual(net.skipped_count, 1)

    def test_run_step_recheck_passes_instructions(self):
        net = _confirmed_network(LeadNetwork.Policy.RECHECK_EACH, extra_instructions="ІНСТР-XYZ")
        lead = _lead(network=net)
        job = self._job()

        def _fake_score(lead_arg, **kwargs):
            lead_arg.ai_verdict = "fit"
            lead_arg.save(update_fields=["ai_verdict"])
            return LeadAICheck.objects.create(
                lead=lead_arg, status=LeadAICheck.Status.DONE, signals={},
            )

        with patch.object(ljob, "checker_can_run", return_value=True), \
                patch.object(lead_checker, "score_lead", side_effect=_fake_score) as score_mock:
            ljob.run_step(job)
            self.assertTrue(score_mock.called)
            self.assertEqual(score_mock.call_args.kwargs.get("extra_instructions"), "ІНСТР-XYZ")
