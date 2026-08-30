"""W1 — безопасность удаления данных клиента (F-SEC-002, F-SEC-003, F-SEC-009).

Эти тесты фиксируют инварианты, которых сейчас нет:

1. Удаление логов не имеет права трогать записи других клиентов
   и системные события (F-SEC-003). Сейчас фильтр `detail__icontains`
   удаляет любую строку, где встречается подстрока идентификатора.
2. Публичная форма `/data-deletion/submit/` не имеет права уничтожать
   данные без подтверждения владения (F-SEC-002).
3. Текст сообщения клиента не должен попадать в `InstagramBotLog.detail`
   (F-SEC-009) — тогда в логе нечего удалять и нечему утекать.
"""
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from management.ig_bot_models import (
    BotDataDeletionRequest,
    IgFollowCtaDecision,
    IgFollowObservation,
    IgFollowRefreshJob,
    IgFollowState,
    IgPaymentFollowPreparation,
    IgUgcEvidenceAssessment,
    IgUgcRewardLifecycleJob,
)
from management.models import (
    IgClient,
    InstagramBotLog,
    InstagramBotMessage,
    InstagramBotRawEvent,
)


@override_settings(ALLOWED_HOSTS=["management.twocomms.shop", "testserver"])
class LogDeletionScopeTests(TestCase):
    """F-SEC-003: удаление логов только по структурированной связи."""

    def test_deletion_keeps_logs_of_other_clients(self):
        from management.bot_views import _delete_direct_bot_records

        target = IgClient.objects.create(igsid="1000000001", username="target_user")
        IgClient.objects.create(igsid="1000000002", username="bystander_user")

        own_log = InstagramBotLog.objects.create(
            level="info", event="queued", detail="1000000001: черга"
        )
        other_log = InstagramBotLog.objects.create(
            level="info", event="queued", detail="1000000002: черга"
        )
        # Лог другого клиента, в тексте которого случайно встречается
        # username удаляемого. Именно это `icontains` и стирает.
        mention_log = InstagramBotLog.objects.create(
            level="info",
            event="observed",
            detail="1000000002: менеджер згадав target_user у розмові",
        )
        system_log = InstagramBotLog.objects.create(
            level="success", event="daemon_start", detail="воркер піднявся"
        )

        result = _delete_direct_bot_records(target.username)

        self.assertFalse(IgClient.objects.filter(pk=target.pk).exists())
        self.assertTrue(
            InstagramBotLog.objects.filter(pk=other_log.pk).exists(),
            "лог другого клиента не должен удаляться",
        )
        self.assertTrue(
            InstagramBotLog.objects.filter(pk=mention_log.pk).exists(),
            "лог другого клиента с упоминанием username не должен удаляться",
        )
        self.assertTrue(
            InstagramBotLog.objects.filter(pk=system_log.pk).exists(),
            "системный лог не должен удаляться",
        )
        self.assertFalse(
            InstagramBotLog.objects.filter(pk=own_log.pk).exists(),
            "лог самого клиента должен удаляться",
        )
        self.assertEqual(result["logs"], 1)

    def test_short_identifier_cannot_wipe_the_whole_log(self):
        """Идентификатор «0» не имеет права снести весь операционный лог."""
        from management.bot_views import _delete_direct_bot_records

        for i in range(5):
            InstagramBotLog.objects.create(
                level="info", event="queued", detail=f"90000000{i}: подія {i}"
            )
        InstagramBotLog.objects.create(
            level="warning", event="bad_signature", detail="Невірний підпис webhook"
        )
        total_before = InstagramBotLog.objects.count()

        result = _delete_direct_bot_records("0")

        self.assertEqual(
            InstagramBotLog.objects.count(),
            total_before,
            "короткий идентификатор без совпадения клиента не должен удалять логи",
        )
        self.assertEqual(result["logs"], 0)

    def test_deletion_by_username_removes_logs_of_that_client_igsid(self):
        """Логи удаляются по igsid клиента, даже если искали по username."""
        from management.bot_views import _delete_direct_bot_records

        IgClient.objects.create(igsid="2000000001", username="byname")
        own = InstagramBotLog.objects.create(
            level="info", event="queued", detail="2000000001: питання про розмір"
        )

        result = _delete_direct_bot_records("byname")

        self.assertFalse(InstagramBotLog.objects.filter(pk=own.pk).exists())
        self.assertEqual(result["logs"], 1)

    def test_deletion_removes_follow_and_ugc_intelligence_before_client(self):
        from management.bot_views import _delete_direct_bot_records

        target = IgClient.objects.create(igsid="2000000011", username="intelligence_user")
        IgFollowState.objects.create(client=target)
        IgFollowObservation.objects.create(
            client=target,
            revision=0,
            trigger="test",
            result=IgFollowObservation.Result.SKIPPED,
            config_fingerprint="f" * 64,
        )
        IgFollowRefreshJob.objects.create(client=target)
        IgFollowCtaDecision.objects.create(
            trigger_key="delete-follow-cta",
            client=target,
            opportunity=IgFollowCtaDecision.Opportunity.PAYMENT,
            state=IgFollowCtaDecision.State.SUPPRESSED,
        )
        lifecycle_job = IgUgcRewardLifecycleJob.objects.create(
            client_id=target.pk,
            source="privacy-test",
        )
        assessment = IgUgcEvidenceAssessment.objects.create(
            client=target,
            source_message_id="delete-source",
            evidence_fingerprint="delete-fingerprint",
        )

        _delete_direct_bot_records(target.username)

        self.assertFalse(IgClient.objects.filter(pk=target.pk).exists())
        self.assertFalse(IgFollowState.objects.filter(client_id=target.pk).exists())
        self.assertFalse(IgFollowObservation.objects.filter(client_id=target.pk).exists())
        self.assertFalse(IgFollowRefreshJob.objects.filter(client_id=target.pk).exists())
        self.assertFalse(IgFollowCtaDecision.objects.filter(client_id=target.pk).exists())
        self.assertFalse(IgUgcEvidenceAssessment.objects.filter(pk=assessment.pk).exists())
        self.assertFalse(
            IgUgcRewardLifecycleJob.objects.filter(pk=lifecycle_job.pk).exists(),
            "lifecycle queue must not retain a deleted client id",
        )

    def test_deletion_removes_payment_follow_preparation_orphan(self):
        """Client-scoped follow preparation must not survive privacy fulfillment."""
        from datetime import timedelta

        from management.bot_views import _delete_direct_bot_records

        target = IgClient.objects.create(igsid="2000000012", username="prep_user")
        preparation = IgPaymentFollowPreparation.objects.create(
            client=target,
            # The lifecycle event is durable and may already be retained; this
            # client-scoped optional-follow job is the data-deletion target.
            lifecycle_event_id=987654,
            deadline_at=timezone.now() + timedelta(minutes=5),
        )

        _delete_direct_bot_records(target.username)

        self.assertFalse(
            IgPaymentFollowPreparation.objects.filter(pk=preparation.pk).exists(),
            "optional follow preparation must not retain a deleted client id",
        )

    def test_privacy_erasure_uses_immediate_two_phase_private_blob_delete(self):
        from django.core.files.base import ContentFile
        from management.bot_views import _delete_direct_bot_records
        from management.services.ig_private_media import private_media_storage

        target = IgClient.objects.create(
            igsid="2000000013",
            username="private_blob_user",
        )
        with tempfile.TemporaryDirectory() as root, override_settings(
            IG_PRIVATE_MEDIA_ROOT=str(Path(root).resolve()),
        ):
            storage = private_media_storage()
            name = storage.save("privacy/audio.ogg", ContentFile(b"private-audio"))
            row = InstagramBotMessage.objects.create(
                sender_id=target.igsid,
                client=target,
                role=InstagramBotMessage.Role.USER,
                private_media_state="active",
                private_media_delete_after=timezone.now() + timedelta(days=3),
                attachment_media=[{
                    "status": "owned",
                    "private_storage": True,
                    "storage_name": name,
                    "mime": "audio/ogg",
                }],
            )

            _delete_direct_bot_records(target.username)

            self.assertFalse(storage.exists(name))
            self.assertFalse(InstagramBotMessage.objects.filter(pk=row.pk).exists())


@override_settings(ALLOWED_HOSTS=["management.twocomms.shop", "testserver"])
class AnonymousDeletionRequestTests(TestCase):
    """F-SEC-002: публичная форма создаёт заявку, а не уничтожает данные."""

    def _post(self, identifier):
        return self.client.post(
            "/data-deletion/submit/",
            {"identifier": identifier},
            HTTP_HOST="management.twocomms.shop",
            secure=True,
            follow=True,
        )

    def test_anonymous_form_does_not_delete_client_data(self):
        client = IgClient.objects.create(igsid="3000000001", username="victim_user")
        InstagramBotMessage.objects.create(
            sender_id="3000000001",
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="історія розмови",
            mid="mid-victim-1",
        )
        InstagramBotRawEvent.objects.create(
            sender_id="3000000001", payload='{"object":"instagram"}'
        )

        response = self._post("https://www.instagram.com/victim_user/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            IgClient.objects.filter(pk=client.pk).exists(),
            "анонимный POST не должен удалять карточку клиента",
        )
        self.assertTrue(
            InstagramBotMessage.objects.filter(sender_id="3000000001").exists(),
            "анонимный POST не должен удалять переписку",
        )
        self.assertTrue(
            InstagramBotRawEvent.objects.filter(sender_id="3000000001").exists(),
            "анонимный POST не должен удалять сырые события",
        )

    def test_anonymous_form_creates_pending_request(self):
        IgClient.objects.create(igsid="3000000002", username="pending_user")

        self._post("pending_user")

        request_row = BotDataDeletionRequest.objects.get()
        self.assertEqual(
            request_row.status,
            BotDataDeletionRequest.Status.PENDING_VERIFICATION,
        )
        self.assertIsNone(request_row.completed_at)
        self.assertEqual(request_row.deleted_clients_count, 0)
        self.assertEqual(request_row.normalized_identifier, "pending_user")

    def test_deletion_alert_omits_identifier_and_confirmation_capability(self):
        marker = "private.delete+marker@example.com"

        with patch("management.bot_views.bot.notify_manager") as notify_manager:
            self._post(marker)

        request_row = BotDataDeletionRequest.objects.get()
        alert = notify_manager.call_args.args[0]
        self.assertNotIn(marker, alert)
        self.assertNotIn(request_row.normalized_identifier, alert)
        self.assertNotIn(request_row.confirmation_code, alert)
        self.assertIn(f"Завдання ID: {request_row.pk}", alert)
        self.assertIn("Статус: pending_verification", alert)

    def test_pending_request_is_visible_on_status_page(self):
        IgClient.objects.create(igsid="3000000003", username="status_user")
        self._post("status_user")
        code = BotDataDeletionRequest.objects.get().confirmation_code

        response = self.client.get(
            f"/data-deletion/status/{code}/",
            HTTP_HOST="management.twocomms.shop",
            secure=True,
        )

        self.assertEqual(response.status_code, 200)

    def test_verified_fulfillment_deletes_data(self):
        """Подтверждённая заявка удаляет данные — компенсация закрытия формы."""
        from management.services.ig_data_deletion import fulfill_deletion_request

        client = IgClient.objects.create(igsid="3000000004", username="fulfil_user")
        InstagramBotMessage.objects.create(
            sender_id="3000000004",
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="видали мене",
            mid="mid-fulfil-1",
        )
        self._post("fulfil_user")
        request_row = BotDataDeletionRequest.objects.get()

        fulfill_deletion_request(request_row, actor_label="manager:test")

        request_row.refresh_from_db()
        self.assertEqual(request_row.status, BotDataDeletionRequest.Status.COMPLETED)
        self.assertIsNotNone(request_row.completed_at)
        self.assertEqual(request_row.deleted_clients_count, 1)
        self.assertFalse(IgClient.objects.filter(pk=client.pk).exists())
        self.assertIn("manager:test", request_row.detail)

    def test_fulfillment_is_idempotent(self):
        from management.services.ig_data_deletion import fulfill_deletion_request

        IgClient.objects.create(igsid="3000000005", username="twice_user")
        self._post("twice_user")
        request_row = BotDataDeletionRequest.objects.get()

        fulfill_deletion_request(request_row, actor_label="manager:test")
        first_detail = BotDataDeletionRequest.objects.get(pk=request_row.pk).detail

        with self.assertRaises(ValueError):
            fulfill_deletion_request(request_row, actor_label="manager:test")

        self.assertEqual(
            BotDataDeletionRequest.objects.get(pk=request_row.pk).detail,
            first_detail,
        )

    def test_deletion_request_row_survives_client_deletion(self):
        """Audit-запись о заявке не должна удаляться вместе с данными."""
        from management.services.ig_data_deletion import fulfill_deletion_request

        IgClient.objects.create(igsid="3000000006", username="audit_user")
        self._post("audit_user")
        request_row = BotDataDeletionRequest.objects.get()

        fulfill_deletion_request(request_row, actor_label="manager:test")

        self.assertTrue(
            BotDataDeletionRequest.objects.filter(pk=request_row.pk).exists(),
            "audit-запись о факте удаления неудаляема",
        )


@override_settings(ALLOWED_HOSTS=["management.twocomms.shop", "testserver"])
class DeletionRateLimitTests(TestCase):
    """F-SEC-002 слой 3: у публичного destructive-эндпоинта свой строгий лимит."""

    def test_submit_path_is_not_in_permissive_webhook_class(self):
        from twocomms.middleware import _RATE_LIMIT_DEFAULTS, _route_rate_limit_name

        request = type(
            "R",
            (),
            {"path": "/data-deletion/submit/", "method": "POST", "META": {}},
        )()

        name = _route_rate_limit_name(request, "management.twocomms.shop")

        self.assertNotEqual(name, "webhook")
        self.assertLessEqual(
            _RATE_LIMIT_DEFAULTS[name],
            30,
            "публичная форма удаления данных должна иметь строгий лимит",
        )


class LogPiiTests(TestCase):
    """F-SEC-009: текст сообщения клиента не пишется в `InstagramBotLog.detail`."""

    def test_inbound_log_detail_omits_message_text(self):
        from management.services.instagram_bot import _inbound_log_detail

        secret_text = "мій номер 0501234567, Нова Пошта 12, Іван Петренко"

        detail = _inbound_log_detail("webhook", "4000000001", secret_text, "")

        self.assertNotIn(secret_text, detail)
        self.assertNotIn("0501234567", detail)
        self.assertNotIn("Петренко", detail)

    def test_inbound_log_detail_keeps_operational_context(self):
        """Диагностическая ценность сохраняется: источник, sender, объём."""
        from management.services.instagram_bot import _inbound_log_detail

        detail = _inbound_log_detail("webhook", "4000000001", "привіт" * 10, " (+2 фото)")

        self.assertIn("webhook", detail)
        self.assertIn("4000000001", detail)
        self.assertIn("60", detail)
        self.assertIn("(+2 фото)", detail)

    def test_inbound_log_detail_handles_empty_text(self):
        from management.services.instagram_bot import _inbound_log_detail

        detail = _inbound_log_detail("webhook", "4000000001", "", "")

        self.assertIn("4000000001", detail)
        self.assertIn("0", detail)
