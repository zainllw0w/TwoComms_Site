import json
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from management.models import (
    IgClient,
    IgFollowCapabilityState,
    IgFollowObservation,
    IgFollowRefreshJob,
    IgFollowState,
    InstagramBotMessage,
    InstagramBotSettings,
)
from management.services import ig_follow_state


class IgFollowStateServiceTests(TestCase):
    def setUp(self):
        self.settings = InstagramBotSettings.load()
        self.settings.ig_user_id = "business-1784"
        self.settings.save(update_fields=["ig_user_id", "updated_at"])
        self.client_record = self._client("follow-state-client")

    def _client(self, igsid):
        client = IgClient.objects.create(
            igsid=igsid,
            first_contact_at=timezone.now(),
            last_message_at=timezone.now(),
        )
        InstagramBotMessage.objects.create(
            sender_id=igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="Привіт",
            status=InstagramBotMessage.Status.DONE,
        )
        return client

    def _request_and_run(self, client=None, *, response=(200, '{}'), trigger="payment"):
        client = client or self.client_record
        job = ig_follow_state.request_follow_refresh(client, trigger=trigger)
        with patch.dict(
            "os.environ",
            {
                "IG_PROVIDER_TRANSPORT": "instagram_login",
                "IG_INSTAGRAM_BOT": "test-follow-token",
            },
            clear=False,
        ), patch(
            "management.services.instagram_bot.get_page_token",
            return_value="effective-token",
        ), patch(
            "management.services.instagram_bot._provider_http",
            return_value=response,
        ) as provider_http:
            result = ig_follow_state.run_follow_refresh_job(job.pk)
        return result, provider_http

    def test_exact_meta_boolean_false_publishes_fresh_not_following(self):
        result, provider_http = self._request_and_run(
            response=(
                200,
                json.dumps({
                    "id": self.client_record.igsid,
                    "is_user_follow_business": False,
                }),
            )
        )

        self.assertEqual(result, "known")
        state = IgFollowState.objects.get(client=self.client_record)
        self.assertEqual(state.state, IgFollowState.State.NOT_FOLLOWING)
        self.assertEqual(state.revision, 1)
        self.assertEqual(state.last_result, IgFollowState.CheckResult.KNOWN)
        self.assertGreater(state.expires_at, state.observed_at)
        call = provider_http.call_args
        self.assertEqual(call.args[1], (
            "https://graph.instagram.com/v25.0/follow-state-client"
            "?fields=is_user_follow_business"
        ))
        self.assertEqual(call.kwargs["token"], "effective-token")
        observation = IgFollowObservation.objects.get(client=self.client_record)
        self.assertIs(observation.observed_value, False)
        self.assertTrue(observation.field_present)
        self.assertEqual(observation.field_type, "bool")

    def test_first_observed_following_timestamp_is_set_once(self):
        first_at = timezone.now()
        with patch("management.services.ig_follow_state.timezone.now", return_value=first_at):
            self._request_and_run(response=(200, json.dumps({
                "id": self.client_record.igsid,
                "is_user_follow_business": True,
            })))
        state = IgFollowState.objects.get(client=self.client_record)
        self.assertEqual(state.first_observed_following_at, first_at)

        second_at = first_at + timedelta(days=2)
        with patch("management.services.ig_follow_state.timezone.now", return_value=second_at):
            ig_follow_state.request_follow_refresh(self.client_record, trigger="post_delivery")
            self._request_and_run(response=(200, json.dumps({
                "id": self.client_record.igsid,
                "is_user_follow_business": True,
            })), trigger="post_delivery")

        state.refresh_from_db()
        self.assertEqual(state.first_observed_following_at, first_at)
        self.assertEqual(state.revision, 2)

    def test_missing_non_boolean_malformed_and_id_mismatch_never_become_known(self):
        invalid_bodies = [
            json.dumps({"id": self.client_record.igsid}),
            json.dumps({"id": self.client_record.igsid, "is_user_follow_business": None}),
            json.dumps({"id": self.client_record.igsid, "is_user_follow_business": "false"}),
            json.dumps({"id": "somebody-else", "is_user_follow_business": False}),
            "not-json",
        ]

        for index, body in enumerate(invalid_bodies, start=1):
            client = self._client(f"invalid-follow-{index}")
            result, _provider = self._request_and_run(client, response=(200, body))
            state = IgFollowState.objects.get(client=client)
            with self.subTest(index=index):
                self.assertEqual(result, "error")
                self.assertEqual(state.state, IgFollowState.State.UNKNOWN)
                self.assertEqual(state.revision, 0)
                self.assertEqual(state.last_result, IgFollowState.CheckResult.ERROR)

    def test_provider_error_preserves_display_observation_but_effective_state_is_unknown(self):
        now = timezone.now()
        state = IgFollowState.objects.create(
            client=self.client_record,
            state=IgFollowState.State.FOLLOWING,
            revision=4,
            source="instagram_login",
            graph_version="v25.0",
            config_fingerprint=ig_follow_state.configuration_fingerprint(self.settings),
            observed_at=now,
            expires_at=now + timedelta(days=7),
            last_result=IgFollowState.CheckResult.KNOWN,
        )

        result, _provider = self._request_and_run(response=(500, "provider down"))

        self.assertEqual(result, "error")
        state.refresh_from_db()
        self.assertEqual(state.state, IgFollowState.State.FOLLOWING)
        self.assertEqual(state.revision, 4)
        self.assertEqual(state.last_result, IgFollowState.CheckResult.ERROR)
        view = ig_follow_state.effective_follow_state(self.client_record, now=now)
        self.assertEqual(view.state, IgFollowState.State.UNKNOWN)
        self.assertEqual(view.last_known_state, IgFollowState.State.FOLLOWING)
        self.assertTrue(view.stale)

    def test_no_local_inbound_consent_skips_before_provider_io(self):
        client = IgClient.objects.create(igsid="no-consent")
        job = ig_follow_state.request_follow_refresh(client, trigger="payment")

        with patch(
            "management.services.instagram_bot._provider_http"
        ) as provider_http:
            result = ig_follow_state.run_follow_refresh_job(job.pk)

        self.assertEqual(result, "skipped")
        provider_http.assert_not_called()
        state = IgFollowState.objects.get(client=client)
        self.assertEqual(state.last_result, IgFollowState.CheckResult.SKIPPED)
        self.assertEqual(state.last_error_kind, "missing_messaging_consent")

    def test_legacy_transport_skips_before_provider_io(self):
        job = ig_follow_state.request_follow_refresh(self.client_record, trigger="payment")

        with patch.dict(
            "os.environ",
            {"IG_PROVIDER_TRANSPORT": "legacy_page", "IG_INSTAGRAM_BOT": ""},
            clear=False,
        ), patch(
            "management.services.instagram_bot._provider_http"
        ) as provider_http:
            result = ig_follow_state.run_follow_refresh_job(job.pk)

        self.assertEqual(result, "skipped")
        provider_http.assert_not_called()
        state = IgFollowState.objects.get(client=self.client_record)
        self.assertEqual(state.last_error_kind, "unsupported_transport")

    def test_refresh_requests_coalesce_and_increment_generation(self):
        first = ig_follow_state.request_follow_refresh(self.client_record, trigger="payment")
        second = ig_follow_state.request_follow_refresh(self.client_record, trigger="hesitation")

        self.assertEqual(first.pk, second.pk)
        second.refresh_from_db()
        self.assertEqual(second.requested_generation, 2)
        self.assertEqual(second.triggers, ["payment", "hesitation"])
        state = IgFollowState.objects.get(client=self.client_record)
        self.assertEqual(state.refresh_generation, 2)

    def test_stale_generation_cannot_publish_provider_result(self):
        job = ig_follow_state.request_follow_refresh(self.client_record, trigger="payment")

        def race_request(*args, **kwargs):
            ig_follow_state.request_follow_refresh(self.client_record, trigger="hesitation")
            return 200, json.dumps({
                "id": self.client_record.igsid,
                "is_user_follow_business": False,
            })

        with patch.dict(
            "os.environ",
            {
                "IG_PROVIDER_TRANSPORT": "instagram_login",
                "IG_INSTAGRAM_BOT": "test-follow-token",
            },
            clear=False,
        ), patch(
            "management.services.instagram_bot.get_page_token",
            return_value="effective-token",
        ), patch(
            "management.services.instagram_bot._provider_http",
            side_effect=race_request,
        ):
            result = ig_follow_state.run_follow_refresh_job(job.pk)

        self.assertEqual(result, "superseded")
        state = IgFollowState.objects.get(client=self.client_record)
        self.assertEqual(state.revision, 0)
        job.refresh_from_db()
        self.assertEqual(job.status, IgFollowRefreshJob.Status.PENDING)
        self.assertEqual(job.requested_generation, 2)

    def test_permission_failure_opens_global_circuit_for_same_configuration(self):
        first_job = ig_follow_state.request_follow_refresh(self.client_record, trigger="payment")
        second_client = self._client("follow-circuit-second")

        with patch.dict(
            "os.environ",
            {
                "IG_PROVIDER_TRANSPORT": "instagram_login",
                "IG_INSTAGRAM_BOT": "test-follow-token",
            },
            clear=False,
        ), patch(
            "management.services.instagram_bot.get_page_token",
            return_value="effective-token",
        ), patch(
            "management.services.instagram_bot._provider_http",
            return_value=(403, json.dumps({"error": {"code": 200}})),
        ) as provider_http:
            first = ig_follow_state.run_follow_refresh_job(first_job.pk)
            second_job = ig_follow_state.request_follow_refresh(
                second_client,
                trigger="payment",
            )
            second = ig_follow_state.run_follow_refresh_job(second_job.pk)

        self.assertEqual(first, "error")
        self.assertEqual(second, "circuit_open")
        self.assertEqual(provider_http.call_count, 1)
        capability = IgFollowCapabilityState.objects.get(singleton_key=1)
        self.assertEqual(capability.status, IgFollowCapabilityState.Status.BLOCKED)
        self.assertGreater(capability.blocked_until, timezone.now())

    def test_configuration_change_invalidates_known_observation(self):
        now = timezone.now()
        with patch.dict(
            "os.environ",
            {
                "IG_PROVIDER_TRANSPORT": "instagram_login",
                "IG_INSTAGRAM_BOT": "old-token",
            },
            clear=False,
        ):
            old_fingerprint = ig_follow_state.configuration_fingerprint(self.settings)
        IgFollowState.objects.create(
            client=self.client_record,
            state=IgFollowState.State.NOT_FOLLOWING,
            revision=2,
            source="instagram_login",
            graph_version="v25.0",
            config_fingerprint=old_fingerprint,
            observed_at=now,
            expires_at=now + timedelta(days=1),
            last_result=IgFollowState.CheckResult.KNOWN,
        )

        with patch.dict(
            "os.environ",
            {
                "IG_PROVIDER_TRANSPORT": "instagram_login",
                "IG_INSTAGRAM_BOT": "rotated-token",
            },
            clear=False,
        ):
            view = ig_follow_state.effective_follow_state(self.client_record, now=now)

        self.assertEqual(view.state, IgFollowState.State.UNKNOWN)
        self.assertEqual(view.last_known_state, IgFollowState.State.NOT_FOLLOWING)
        self.assertTrue(view.stale)

    def test_pre_provider_skip_cannot_drop_newer_generation(self):
        client = IgClient.objects.create(igsid="skip-race")
        job = ig_follow_state.request_follow_refresh(client, trigger="payment")

        def consent_race(_client_id):
            ig_follow_state.request_follow_refresh(client, trigger="hesitation")
            return False

        with patch(
            "management.services.ig_follow_state._messaging_consent_exists",
            side_effect=consent_race,
        ):
            result = ig_follow_state.run_follow_refresh_job(job.pk)

        self.assertEqual(result, "superseded")
        job.refresh_from_db()
        self.assertEqual(job.status, IgFollowRefreshJob.Status.PENDING)
        self.assertEqual(job.requested_generation, 2)
        self.assertEqual(IgFollowObservation.objects.filter(client=client).count(), 0)

    def test_missing_token_opens_global_circuit(self):
        first_job = ig_follow_state.request_follow_refresh(
            self.client_record,
            trigger="payment",
        )
        second_client = self._client("missing-token-second")

        with patch.dict(
            "os.environ",
            {
                "IG_PROVIDER_TRANSPORT": "instagram_login",
                "IG_INSTAGRAM_BOT": "missing-token",
            },
            clear=False,
        ), patch(
            "management.services.instagram_bot.get_page_token",
            return_value="",
        ), patch(
            "management.services.instagram_bot._provider_http"
        ) as provider_http:
            first = ig_follow_state.run_follow_refresh_job(first_job.pk)
            second_job = ig_follow_state.request_follow_refresh(
                second_client,
                trigger="payment",
            )
            second = ig_follow_state.run_follow_refresh_job(second_job.pk)

        self.assertEqual(first, "error")
        self.assertEqual(second, "circuit_open")
        provider_http.assert_not_called()
        capability = IgFollowCapabilityState.objects.get(singleton_key=1)
        self.assertEqual(capability.status, IgFollowCapabilityState.Status.BLOCKED)

    def test_rate_limit_opens_degraded_circuit_for_other_clients(self):
        first_job = ig_follow_state.request_follow_refresh(
            self.client_record,
            trigger="payment",
        )
        second_client = self._client("rate-limit-second")

        with patch.dict(
            "os.environ",
            {
                "IG_PROVIDER_TRANSPORT": "instagram_login",
                "IG_INSTAGRAM_BOT": "rate-limit-token",
            },
            clear=False,
        ), patch(
            "management.services.instagram_bot.get_page_token",
            return_value="effective-token",
        ), patch(
            "management.services.instagram_bot._provider_http",
            return_value=(429, "rate limited"),
        ) as provider_http:
            first = ig_follow_state.run_follow_refresh_job(first_job.pk)
            second_job = ig_follow_state.request_follow_refresh(
                second_client,
                trigger="payment",
            )
            second = ig_follow_state.run_follow_refresh_job(second_job.pk)

        self.assertEqual(first, "error")
        self.assertEqual(second, "circuit_open")
        self.assertEqual(provider_http.call_count, 1)
        capability = IgFollowCapabilityState.objects.get(singleton_key=1)
        self.assertEqual(capability.status, IgFollowCapabilityState.Status.DEGRADED)

    def test_provider_timeout_is_persisted_as_transport_error(self):
        job = ig_follow_state.request_follow_refresh(
            self.client_record,
            trigger="hesitation",
        )
        with patch.dict(
            "os.environ",
            {
                "IG_PROVIDER_TRANSPORT": "instagram_login",
                "IG_INSTAGRAM_BOT": "timeout-token",
            },
            clear=False,
        ), patch(
            "management.services.instagram_bot.get_page_token",
            return_value="effective-token",
        ), patch(
            "management.services.instagram_bot._provider_http",
            side_effect=TimeoutError("Meta timed out"),
        ):
            result = ig_follow_state.run_follow_refresh_job(job.pk)

        self.assertEqual(result, "error")
        observation = IgFollowObservation.objects.get(client=self.client_record)
        self.assertEqual(observation.error_kind, "transport")
        self.assertEqual(observation.error_code, "TimeoutError")

    def test_token_or_url_setup_exception_is_published_as_error(self):
        job = ig_follow_state.request_follow_refresh(
            self.client_record,
            trigger="payment",
        )

        with patch.dict(
            "os.environ",
            {
                "IG_PROVIDER_TRANSPORT": "instagram_login",
                "IG_INSTAGRAM_BOT": "setup-error-token",
            },
            clear=False,
        ), patch(
            "management.services.instagram_bot.get_page_token",
            side_effect=RuntimeError("token decrypt failed"),
        ):
            result = ig_follow_state.run_follow_refresh_job(job.pk)

        self.assertEqual(result, "error")
        job.refresh_from_db()
        self.assertEqual(job.status, IgFollowRefreshJob.Status.FAILED)
        state = IgFollowState.objects.get(client=self.client_record)
        self.assertEqual(state.last_result, IgFollowState.CheckResult.ERROR)
        self.assertEqual(state.last_error_kind, "provider_setup")

    def test_completed_job_is_idempotent_without_a_new_generation(self):
        job = ig_follow_state.request_follow_refresh(
            self.client_record,
            trigger="payment",
        )
        response = (
            200,
            json.dumps({
                "id": self.client_record.igsid,
                "is_user_follow_business": False,
            }),
        )
        with patch.dict(
            "os.environ",
            {
                "IG_PROVIDER_TRANSPORT": "instagram_login",
                "IG_INSTAGRAM_BOT": "done-idempotent-token",
            },
            clear=False,
        ), patch(
            "management.services.instagram_bot.get_page_token",
            return_value="effective-token",
        ), patch(
            "management.services.instagram_bot._provider_http",
            return_value=response,
        ) as provider_http:
            first = ig_follow_state.run_follow_refresh_job(job.pk)
            second = ig_follow_state.run_follow_refresh_job(
                job.pk,
                now=timezone.now() + timedelta(days=2),
            )

        self.assertEqual(first, "known")
        self.assertEqual(second, "done")
        self.assertEqual(provider_http.call_count, 1)
        state = IgFollowState.objects.get(client=self.client_record)
        self.assertEqual(state.revision, 1)

    def test_negative_graph_codes_are_discarded_before_persistence(self):
        job = ig_follow_state.request_follow_refresh(
            self.client_record,
            trigger="payment",
        )
        body = json.dumps({
            "error": {"code": -7, "error_subcode": -11},
        })
        with patch.dict(
            "os.environ",
            {
                "IG_PROVIDER_TRANSPORT": "instagram_login",
                "IG_INSTAGRAM_BOT": "negative-code-token",
            },
            clear=False,
        ), patch(
            "management.services.instagram_bot.get_page_token",
            return_value="effective-token",
        ), patch(
            "management.services.instagram_bot._provider_http",
            return_value=(400, body),
        ):
            result = ig_follow_state.run_follow_refresh_job(job.pk)

        self.assertEqual(result, "error")
        observation = IgFollowObservation.objects.get(client=self.client_record)
        self.assertIsNone(observation.graph_code)
        self.assertIsNone(observation.graph_subcode)

    def test_refresh_if_due_skips_fresh_state_without_provider_io(self):
        now = timezone.now()
        with patch.dict(
            "os.environ",
            {
                "IG_PROVIDER_TRANSPORT": "instagram_login",
                "IG_INSTAGRAM_BOT": "fresh-state-token",
            },
            clear=False,
        ):
            fingerprint = ig_follow_state.configuration_fingerprint(self.settings)
            IgFollowState.objects.create(
                client=self.client_record,
                state=IgFollowState.State.NOT_FOLLOWING,
                revision=3,
                source="instagram_login",
                graph_version="v25.0",
                config_fingerprint=fingerprint,
                observed_at=now,
                expires_at=now + timedelta(hours=1),
                last_result=IgFollowState.CheckResult.KNOWN,
            )
            with patch(
                "management.services.instagram_bot._provider_http"
            ) as provider_http:
                result = ig_follow_state.refresh_follow_state_if_due(
                    self.client_record,
                    trigger="hesitation",
                    now=now + timedelta(minutes=1),
                )

        self.assertEqual(result, "fresh")
        provider_http.assert_not_called()
        self.assertFalse(IgFollowRefreshJob.objects.filter(client=self.client_record).exists())

    def test_refresh_if_due_respects_client_backoff_without_provider_io(self):
        now = timezone.now()
        with patch.dict(
            "os.environ",
            {
                "IG_PROVIDER_TRANSPORT": "instagram_login",
                "IG_INSTAGRAM_BOT": "backoff-token",
            },
            clear=False,
        ), patch(
            "management.services.instagram_bot.get_page_token",
            return_value="effective-token",
        ), patch(
            "management.services.instagram_bot._provider_http",
            return_value=(500, "provider down"),
        ) as provider_http:
            first = ig_follow_state.refresh_follow_state_if_due(
                self.client_record,
                trigger="payment",
                now=now,
            )
            state = IgFollowState.objects.get(client=self.client_record)
            self.assertEqual(first, "error")
            retry_at = state.next_retry_at
            self.assertIsNotNone(retry_at)
            provider_http.reset_mock()
            second = ig_follow_state.refresh_follow_state_if_due(
                self.client_record,
                trigger="hesitation",
                now=retry_at - timedelta(seconds=1),
            )

        self.assertEqual(second, "backoff")
        provider_http.assert_not_called()
        state.refresh_from_db()
        self.assertEqual(state.refresh_generation, 1)
