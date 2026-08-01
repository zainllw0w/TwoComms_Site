"""W3 / IMP-014 — «оплачено» перестаёт быть недостижимым состоянием (F-SCORE-003).

`_normalize` принудительно понижала `paid → checkout` и
`paid_order_waiting → payment_pending` **всегда**, даже когда факт оплаты
подтверждён самой системой. Логика понижения имеет смысл, пока «оплачено» —
это утверждение модели: слова клиента деньгами не являются. Но когда оплату
подтвердил провайдер или менеджер, понижать нечего — мы затираем собственную
истину и клиент навсегда остаётся «в процессе оплаты».

На проде это проверялось: `score_band='paid'` — 0 записей из 1792.

Инвариант: при `verified_payment=True` состояние «оплачено» сохраняется;
при `verified_payment=False` понижение остаётся, и причина фиксируется.
"""
from decimal import Decimal

from django.test import SimpleTestCase

from management.models import IgConversationAnalysisSnapshot


class PaidBandNormalizationTests(SimpleTestCase):
    Band = IgConversationAnalysisSnapshot.Band
    Types = IgConversationAnalysisSnapshot.InteractionType

    def _normalize(self, *, band, interaction_type, verified_payment, probability="0.9900"):
        from management.services.bot_conversation_analysis import _normalize

        parsed = {
            "score_band": band,
            "interaction_type": interaction_type,
            "purchase_probability": probability,
            "confidence": "0.9000",
            "summary": "клієнт оплатив замовлення",
            "uncertainties": [],
        }
        return _normalize(parsed, {}, verified_payment=verified_payment)

    # ------------------------------------------ подтверждённая оплата
    def test_verified_payment_keeps_paid_band(self):
        result = self._normalize(
            band=self.Band.PAID,
            interaction_type=self.Types.PAID_ORDER_WAITING,
            verified_payment=True,
        )

        self.assertEqual(
            result["score_band"],
            self.Band.PAID,
            "при подтверждённой оплате состояние «оплачено» затирать нельзя",
        )

    def test_verified_payment_keeps_paid_order_waiting(self):
        result = self._normalize(
            band=self.Band.PAID,
            interaction_type=self.Types.PAID_ORDER_WAITING,
            verified_payment=True,
        )

        self.assertEqual(result["interaction_type"], self.Types.PAID_ORDER_WAITING)

    def test_verified_payment_does_not_cap_probability(self):
        result = self._normalize(
            band=self.Band.PAID,
            interaction_type=self.Types.PAID_ORDER_WAITING,
            verified_payment=True,
            probability="1.0000",
        )

        self.assertEqual(Decimal(str(result["purchase_probability"])), Decimal("1.0000"))

    def test_verified_payment_adds_no_unverified_marker(self):
        result = self._normalize(
            band=self.Band.PAID,
            interaction_type=self.Types.PAID_ORDER_WAITING,
            verified_payment=True,
        )

        self.assertNotIn("payment_unverified", result.get("uncertainties") or [])

    # -------------------------------------- неподтверждённая оплата
    def test_unverified_payment_still_downgrades(self):
        """Слова клиента деньгами не являются — понижение остаётся."""
        result = self._normalize(
            band=self.Band.PAID,
            interaction_type=self.Types.PAID_ORDER_WAITING,
            verified_payment=False,
        )

        self.assertEqual(result["score_band"], self.Band.CHECKOUT)
        self.assertEqual(result["interaction_type"], self.Types.PAYMENT_PENDING)
        self.assertIn("payment_unverified", result.get("uncertainties") or [])

    def test_unverified_payment_caps_probability(self):
        result = self._normalize(
            band=self.Band.PAID,
            interaction_type=self.Types.PAID_ORDER_WAITING,
            verified_payment=False,
            probability="1.0000",
        )

        self.assertLessEqual(
            Decimal(str(result["purchase_probability"])), Decimal("0.9500")
        )

    def test_unverified_paid_order_waiting_without_paid_band_downgrades(self):
        result = self._normalize(
            band=self.Band.CHECKOUT,
            interaction_type=self.Types.PAID_ORDER_WAITING,
            verified_payment=False,
        )

        self.assertEqual(result["interaction_type"], self.Types.PAYMENT_PENDING)

    def test_other_bands_are_untouched(self):
        result = self._normalize(
            band=self.Band.HIGH_INTENT,
            interaction_type=self.Types.PRODUCT_INTEREST,
            verified_payment=True,
        )

        self.assertEqual(result["score_band"], self.Band.HIGH_INTENT)
        self.assertEqual(result["interaction_type"], self.Types.PRODUCT_INTEREST)


class PaidBandCardDisplayTests(SimpleTestCase):
    """Дубль понижения в карточке клиента (`bot_views`) — та же семантика."""

    def test_card_band_helper_keeps_paid_when_payment_verified(self):
        from management.bot_views import _display_band

        self.assertEqual(
            _display_band(
                IgConversationAnalysisSnapshot.Band.PAID, verified_payment=True
            ),
            IgConversationAnalysisSnapshot.Band.PAID,
        )

    def test_card_band_helper_downgrades_unverified_paid(self):
        from management.bot_views import _display_band

        self.assertEqual(
            _display_band(
                IgConversationAnalysisSnapshot.Band.PAID, verified_payment=False
            ),
            IgConversationAnalysisSnapshot.Band.CHECKOUT,
        )
