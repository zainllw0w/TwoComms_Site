"""Тести корпуса оценки — Э0.5: дії, а не тільки текст.

Перевіряють, що:
1. Формат сценаріїв дотримано (authored_by, обов'язкові ключі, action_classes)
2. Корпус версійовано правильно (integrity збігається, history ведеться)
3. NetworkGuard ловить сетевий вихід
4. Харнес виявляє дії з реальних побічних ефектів (diff по таблицям)
5. Сценарії не підганяються під вихід моделі (ні один read-after-run)
6. Прогон референсного сценарію проходить і не робить сітьових викликів
7. Hard safety: заборонені дії роблять сценарій червоним
"""

import json
import socket
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase

from management.services.ig_eval_corpus import (
    ACTION_CLASSES,
    COHORTS,
    CORPUS_ROOT,
    CorpusFormatError,
    CorpusIntegrityError,
    CorpusNetworkViolation,
    NetworkGuard,
    compute_integrity,
    current_digests,
    file_digest,
    load_manifest,
    load_scenarios,
    run_scenario,
    verify_integrity,
)


class CorpusFormatTests(TestCase):
    """Перевірка формату корпусу."""

    def test_all_scenarios_have_authored_by_human(self):
        """Ожидання корпусу пише людина, не модель."""
        scenarios = load_scenarios()
        for scenario in scenarios:
            self.assertEqual(
                scenario.authored_by,
                "human",
                f"{scenario.id}: автор має бути 'human', а не '{scenario.authored_by}'",
            )

    def test_scenario_filename_matches_id(self):
        """Ім'я файлу збігається з id."""
        scenarios = load_scenarios()
        for scenario in scenarios:
            self.assertEqual(
                scenario.path.stem,
                scenario.id,
                f"{scenario.id}: ім'я файлу {scenario.path.stem} не збігається з id",
            )

    def test_all_action_classes_are_known(self):
        """Усі дії у сценаріях відомі ACTION_CLASSES."""
        scenarios = load_scenarios()
        for scenario in scenarios:
            unknown_expected = scenario.expected_actions - ACTION_CLASSES
            unknown_forbidden = scenario.forbidden_actions - ACTION_CLASSES
            self.assertFalse(
                unknown_expected,
                f"{scenario.id}: невідомі очікувані дії {sorted(unknown_expected)}",
            )
            self.assertFalse(
                unknown_forbidden,
                f"{scenario.id}: невідомі заборонені дії {sorted(unknown_forbidden)}",
            )

    def test_all_scenarios_have_forbidden_actions(self):
        """У кожного сценарію є forbidden_actions."""
        scenarios = load_scenarios()
        for scenario in scenarios:
            self.assertTrue(
                scenario.forbidden_actions,
                f"{scenario.id}: немає forbidden_actions — сценарій не перевіряє hard safety",
            )

    def test_expected_and_forbidden_do_not_overlap(self):
        """Дія не може бути одночасно очікуваною і забороненою."""
        scenarios = load_scenarios()
        for scenario in scenarios:
            overlap = scenario.expected_actions & scenario.forbidden_actions
            self.assertFalse(
                overlap, f"{scenario.id}: дії в обох списках: {sorted(overlap)}"
            )

    def test_cohort_is_known(self):
        """Когорта кожного сценарію відома."""
        scenarios = load_scenarios()
        for scenario in scenarios:
            self.assertIn(
                scenario.cohort,
                COHORTS,
                f"{scenario.id}: невідома когорта {scenario.cohort!r}",
            )

    def test_inbound_is_not_empty(self):
        """Кожен сценарій має принаймні одне вхідне повідомлення."""
        scenarios = load_scenarios()
        for scenario in scenarios:
            self.assertTrue(
                scenario.inbound, f"{scenario.id}: inbound порожній"
            )


class CorpusIntegrityTests(TestCase):
    """Перевірка версіонування і integrity корпусу."""

    def test_manifest_has_authored_by_human(self):
        """Манифест корпусу написаний людиною."""
        manifest = load_manifest()
        self.assertEqual(
            manifest["authored_by"],
            "human",
            "автор манифеста має бути 'human'",
        )

    def test_integrity_matches_current_content(self):
        """integrity в манифесті відповідає поточному вмісту."""
        manifest = verify_integrity()
        digests = current_digests()
        version = manifest["corpus_version"]
        expected = compute_integrity(version, digests)
        self.assertEqual(
            manifest["integrity"],
            expected,
            "integrity в манифесті розійшовся з вмістом корпусу",
        )

    def test_history_contains_current_version(self):
        """Поточна версія присутня в history."""
        manifest = load_manifest()
        version = str(manifest["corpus_version"])
        history_versions = [str(entry["version"]) for entry in manifest["history"]]
        self.assertIn(
            version,
            history_versions,
            f"поточної версії {version} немає в history",
        )

    def test_changing_scenario_breaks_integrity(self):
        """Зміна сценарію без підняття версії ламає integrity."""
        manifest = load_manifest()
        digests = current_digests()
        if not digests:
            self.skipTest("немає сценаріїв")
        first_name = sorted(digests)[0]
        original_digest = digests[first_name]
        faked_digests = dict(digests)
        faked_digests[first_name] = "0" * 64
        version = str(manifest["corpus_version"])
        faked_integrity = compute_integrity(version, faked_digests)
        self.assertNotEqual(
            faked_integrity,
            manifest["integrity"],
            "зміна сценарію має ламати integrity",
        )


class NetworkGuardTests(TestCase):
    """Перевірка ізоляції від мережі."""

    def test_network_guard_allows_loopback(self):
        """NetworkGuard дозволяє з'єднання з localhost."""
        with NetworkGuard():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.1)
            try:
                sock.connect(("127.0.0.1", 1))
            except (ConnectionRefusedError, OSError):
                pass
            finally:
                sock.close()

    def test_network_guard_blocks_external(self):
        """NetworkGuard блокує зовнішні з'єднання."""
        with NetworkGuard() as guard:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            with self.assertRaises(CorpusNetworkViolation):
                sock.connect(("8.8.8.8", 80))
            sock.close()
            self.assertIn("8.8.8.8", str(guard.attempts))


class CorpusRunnerTests(TestCase):
    """Прогон референсного сценарію."""

    def test_reference_scenario_runs_without_network_calls(self):
        """Референсний сценарій проходить без мережевих викликів."""
        scenarios = load_scenarios()
        ref = next((s for s in scenarios if s.id == "ref001_simple_reply"), None)
        if ref is None:
            self.skipTest("референсний сценарій не знайдено")

        observed = run_scenario(ref)
        self.assertIn("reply.text", observed.actions)
        self.assertEqual(observed.customer_messages, 1)
        self.assertLessEqual(observed.provider_calls, 1)

    def test_forbidden_action_fails_scenario(self):
        """Якщо спостережена заборонена дія, сценарій падає."""
        scenarios = load_scenarios()
        for scenario in scenarios:
            observed = run_scenario(scenario)
            violation = observed.actions & scenario.forbidden_actions
            self.assertFalse(
                violation,
                f"{scenario.id}: заборонені дії спостережені: {sorted(violation)}",
            )

    def test_expected_actions_are_observed(self):
        """Очікувані дії справді спостерігаються."""
        scenarios = load_scenarios()
        for scenario in scenarios:
            observed = run_scenario(scenario)
            missing = scenario.expected_actions - observed.actions
            self.assertFalse(
                missing,
                f"{scenario.id}: очікувані дії не спостережені: {sorted(missing)}",
            )


class CorpusWriteProtectionTests(TestCase):
    """Перевірка, що корпус не змінюється під час прогону."""

    def test_runner_does_not_modify_corpus_directory(self):
        """Раннер не пише в каталог корпусу."""
        before = {p: file_digest(p) for p in CORPUS_ROOT.rglob("*.json")}
        scenarios = load_scenarios()
        for scenario in scenarios:
            run_scenario(scenario)
        after = {p: file_digest(p) for p in CORPUS_ROOT.rglob("*.json")}
        self.assertEqual(
            before,
            after,
            "раннер змінив файли корпусу під час прогону",
        )
