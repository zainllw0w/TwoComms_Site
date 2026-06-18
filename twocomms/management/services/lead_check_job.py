"""Движок AI-чекера: браузер-driven stepping (как парсер). Один лид на шаг,
результат сразу в БД, единственная активная сессия через RuntimeLock."""
from __future__ import annotations

import datetime
import logging

from django.db import transaction
from django.utils import timezone

from management.models import (
    LeadAICheck,
    LeadCheckJob,
    LeadCheckRuntimeLock,
    LeadCheckerSettings,
    ManagementLead,
)
from management.services import lead_checker
from management.services import gemini_keys

logger = logging.getLogger("management.checker")

ACTIVE_STATUSES = {LeadCheckJob.Status.RUNNING, LeadCheckJob.Status.PAUSED}

CHECKER_ROLE = "checker"


class CheckerServiceError(Exception):
    pass


def resolve_checker_api_key() -> str:
    return (LeadCheckerSettings.load().gemini_api_key or "").strip()


def checker_can_run() -> bool:
    """Чи можна зараз робити grounded-перевірку: є ручний ключ або вільний
    ключ checker-пулу (не в кулдауні)."""
    if resolve_checker_api_key():
        return True
    return gemini_keys.has_available_key(CHECKER_ROLE)


def candidate_queryset(*, scope: str, city: str, band: str):
    base = ManagementLead.objects.filter(lead_source=ManagementLead.LeadSource.PARSER)
    if scope == "all":
        return base.order_by("id")
    if scope == "by_city":
        return base.filter(city__iexact=(city or "").strip(), ai_checked_at__isnull=True).order_by("id")
    if scope == "by_band":
        return base.filter(ai_verdict=(band or "").strip()).order_by("id")
    # default: unchecked
    return base.filter(ai_checked_at__isnull=True).order_by("id")


def _lock_for_update() -> LeadCheckRuntimeLock:
    lock, _ = LeadCheckRuntimeLock.objects.select_for_update().get_or_create(singleton_key=1)
    return lock


def _normalize_active(lock: LeadCheckRuntimeLock) -> LeadCheckJob | None:
    job = lock.active_job
    if job and job.status not in ACTIVE_STATUSES:
        lock.active_job = None
        lock.save(update_fields=["active_job", "updated_at"])
        return None
    return job


def create_check_job(*, user, scope, city, band, target_limit, requests_per_minute) -> LeadCheckJob:
    total = candidate_queryset(scope=scope, city=city, band=band).count()
    with transaction.atomic():
        lock = _lock_for_update()
        if _normalize_active(lock):
            raise CheckerServiceError("Вже є активна сесія чекера. Зупиніть її перед новим запуском.")
        job = LeadCheckJob.objects.create(
            created_by=user, status=LeadCheckJob.Status.RUNNING,
            scope=scope or "unchecked", city=(city or "").strip(), band=(band or "").strip(),
            target_limit=max(0, int(target_limit or 0)),
            requests_per_minute=max(1, min(20, int(requests_per_minute or 8))),
            total_selected=total,
        )
        lock.active_job = job
        lock.save(update_fields=["active_job", "updated_at"])
        return job


def pause_job(job_id) -> LeadCheckJob:
    with transaction.atomic():
        job = LeadCheckJob.objects.select_for_update().get(id=job_id)
        if job.status == LeadCheckJob.Status.RUNNING:
            job.status = LeadCheckJob.Status.PAUSED
            job.next_step_not_before = None
            job.save(update_fields=["status", "next_step_not_before", "updated_at"])
        return job


def resume_job(job_id) -> LeadCheckJob:
    with transaction.atomic():
        lock = _lock_for_update()
        active = _normalize_active(lock)
        job = LeadCheckJob.objects.select_for_update().get(id=job_id)
        if active and active.id != job.id:
            raise CheckerServiceError("Вже є інша активна сесія чекера.")
        if job.status == LeadCheckJob.Status.PAUSED:
            job.status = LeadCheckJob.Status.RUNNING
            job.last_error = ""
            job.save(update_fields=["status", "last_error", "updated_at"])
            lock.active_job = job
            lock.save(update_fields=["active_job", "updated_at"])
        return job


def stop_job(job_id, *, reason_code="user_stop") -> LeadCheckJob:
    with transaction.atomic():
        lock = _lock_for_update()
        job = LeadCheckJob.objects.select_for_update().get(id=job_id)
        if job.status in ACTIVE_STATUSES:
            job.status = LeadCheckJob.Status.STOPPED
            job.stop_reason_code = reason_code
            job.finished_at = timezone.now()
            job.next_step_not_before = None
            job.save(update_fields=["status", "stop_reason_code", "finished_at", "next_step_not_before", "updated_at"])
        if lock.active_job_id == job.id:
            lock.active_job = None
            lock.save(update_fields=["active_job", "updated_at"])
        return job


def dashboard_job(job_id=None) -> LeadCheckJob | None:
    if job_id:
        return LeadCheckJob.objects.filter(id=job_id).first()
    with transaction.atomic():
        lock = _lock_for_update()
        active = _normalize_active(lock)
    if active:
        return active
    return LeadCheckJob.objects.order_by("-started_at", "-id").first()


def _next_lead(job: LeadCheckJob):
    qs = candidate_queryset(scope=job.scope, city=job.city, band=job.band)
    return qs.filter(id__gt=job.cursor_id).first()


def _complete(job: LeadCheckJob, reason="completed"):
    job.status = LeadCheckJob.Status.COMPLETED
    job.stop_reason_code = reason
    job.finished_at = timezone.now()
    job.next_step_not_before = None
    job.save()
    with transaction.atomic():
        lock = _lock_for_update()
        if lock.active_job_id == job.id:
            lock.active_job = None
            lock.save(update_fields=["active_job", "updated_at"])


def run_step(job: LeadCheckJob) -> LeadCheckJob:
    job.refresh_from_db()
    if job.status != LeadCheckJob.Status.RUNNING:
        return job

    now = timezone.now()
    if job.next_step_not_before and now < job.next_step_not_before:
        return job

    if job.target_limit and job.processed >= job.target_limit:
        _complete(job, reason="target_reached")
        return job

    lead = _next_lead(job)
    if lead is None:
        _complete(job, reason="exhausted")
        return job

    # Немає вільного ключа checker-пулу → ставимо на паузу з обратним відліком
    # до скидання квоти (опівночі PT). НЕ спалюємо лід у error.
    if not checker_can_run():
        job.status = LeadCheckJob.Status.PAUSED
        job.stop_reason_code = "keys_cooldown"
        job.next_step_not_before = gemini_keys.soonest_cooldown(CHECKER_ROLE)
        job.is_step_in_progress = False
        job.current_lead_id = None
        job.save(update_fields=["status", "stop_reason_code", "next_step_not_before",
                                "is_step_in_progress", "current_lead_id", "updated_at"])
        return job

    job.current_lead_id = lead.id
    job.is_step_in_progress = True
    job.last_step_started_at = now
    job.save(update_fields=["current_lead_id", "is_step_in_progress", "last_step_started_at", "updated_at"])

    api_key = resolve_checker_api_key()
    try:
        check = lead_checker.score_lead(lead, api_key=api_key or None, checked_by=job.created_by, job=job)
    except lead_checker.CheckerKeysExhausted:
        # Ключі вичерпались під час обробки — пауза, лід НЕ споживаємо (cursor не
        # рухаємо, processed не інкрементуємо), повторимо коли квота відновиться.
        job.status = LeadCheckJob.Status.PAUSED
        job.stop_reason_code = "keys_cooldown"
        job.next_step_not_before = gemini_keys.soonest_cooldown(CHECKER_ROLE)
        job.is_step_in_progress = False
        job.current_lead_id = None
        job.save(update_fields=["status", "stop_reason_code", "next_step_not_before",
                                "is_step_in_progress", "current_lead_id", "updated_at"])
        return job
    except Exception as exc:  # noqa: BLE001
        logger.exception("run_step score_lead crashed lead=%s", lead.id)
        job.errors += 1
        job.last_error = f"{type(exc).__name__}: {exc}"
        check = None

    job.processed += 1
    job.cursor_id = lead.id
    if check is not None:
        if check.status == LeadAICheck.Status.DONE:
            job.scored += 1
            band = lead.ai_verdict
            if band == "fit":
                job.fit_count += 1
            elif band == "maybe":
                job.maybe_count += 1
            elif band == "unfit":
                job.unfit_count += 1
        else:
            job.errors += 1
        dur = getattr(check, "_duration_seconds", 0.0) or 0.0
        if job.processed:
            job.avg_seconds = ((job.avg_seconds * (job.processed - 1)) + dur) / job.processed

    interval = 60.0 / max(1, job.requests_per_minute)
    job.next_step_not_before = timezone.now() + datetime.timedelta(seconds=interval)
    job.is_step_in_progress = False
    job.current_lead_id = None
    job.save()

    if job.target_limit and job.processed >= job.target_limit:
        _complete(job, reason="target_reached")
    elif _next_lead(job) is None:
        _complete(job, reason="exhausted")
    return job


def job_status_payload(job: LeadCheckJob | None) -> dict | None:
    if job is None:
        return None
    now = timezone.now()
    eta_ms = 0
    if job.status == LeadCheckJob.Status.RUNNING and job.next_step_not_before:
        delta = (job.next_step_not_before - now).total_seconds()
        eta_ms = max(0, int(delta * 1000))
    elapsed = 0
    if job.started_at:
        end = job.finished_at or now
        elapsed = int((end - job.started_at).total_seconds())
    remaining = max(0, job.total_selected - job.processed)
    keys_cd_iso = None
    keys_cd_secs = 0
    if job.stop_reason_code == "keys_cooldown":
        cd = gemini_keys.soonest_cooldown(CHECKER_ROLE)
        if cd:
            keys_cd_iso = cd.isoformat()
            keys_cd_secs = max(0, int((cd - now).total_seconds()))
    return {
        "id": job.id,
        "status": job.status,
        "is_auto": job.is_auto,
        "scope": job.scope,
        "city": job.city,
        "band": job.band,
        "total_selected": job.total_selected,
        "processed": job.processed,
        "scored": job.scored,
        "errors": job.errors,
        "remaining": remaining,
        "fit_count": job.fit_count,
        "maybe_count": job.maybe_count,
        "unfit_count": job.unfit_count,
        "avg_seconds": round(job.avg_seconds, 1),
        "requests_per_minute": job.requests_per_minute,
        "current_lead_id": job.current_lead_id,
        "is_step_in_progress": job.is_step_in_progress,
        "next_step_eta_ms": eta_ms,
        "elapsed_seconds": elapsed,
        "last_error": job.last_error,
        "stop_reason_code": job.stop_reason_code,
        "keys_cooldown_until": keys_cd_iso,
        "keys_cooldown_seconds": keys_cd_secs,
    }


# ---------------------------------------------------------------------------
# Авто-чекінг (cron): продовжує перевірку, щойно квота відновлюється
# ---------------------------------------------------------------------------
def _get_or_create_auto_job(settings_obj: LeadCheckerSettings) -> LeadCheckJob | None:
    """Повертає авто-джобу для продовження (resume) або створює нову.
    Якщо активна РУЧНА сесія — не втручаємось (None)."""
    with transaction.atomic():
        lock = _lock_for_update()
        active = _normalize_active(lock)
        if active:
            if not active.is_auto:
                return None  # ручна сесія активна — не заважаємо
            if active.status == LeadCheckJob.Status.PAUSED:
                active.status = LeadCheckJob.Status.RUNNING
                active.stop_reason_code = ""
                active.next_step_not_before = None
                active.save(update_fields=["status", "stop_reason_code",
                                           "next_step_not_before", "updated_at"])
            return active
        total = candidate_queryset(scope="unchecked", city="", band="").count()
        if total == 0:
            return None
        job = LeadCheckJob.objects.create(
            created_by=None, is_auto=True, status=LeadCheckJob.Status.RUNNING,
            scope="unchecked", target_limit=0,
            requests_per_minute=max(1, min(20, int(settings_obj.requests_per_minute or 8))),
            total_selected=total,
        )
        lock.active_job = job
        lock.save(update_fields=["active_job", "updated_at"])
        return job


def auto_recheck_tick(*, max_seconds: int = 240, sleeper=None) -> dict:
    """Один прохід cron-команди авто-чекінгу.

    Якщо увімкнено auto_recheck, є вільний ключ checker-пулу та непроверені ліди —
    продовжує/створює авто-джобу та обробляє до auto_recheck_batch лідів, поважаючи
    RPM. Ідемпотентно, безпечно для частого виклику.
    """
    import time as _time
    sleeper = sleeper or _time.sleep
    s = LeadCheckerSettings.load()
    if not s.auto_recheck:
        return {"ran": False, "reason": "disabled"}
    if not checker_can_run():
        return {"ran": False, "reason": "keys_cooldown"}
    if not candidate_queryset(scope="unchecked", city="", band="").exists():
        return {"ran": False, "reason": "no_unchecked"}

    job = _get_or_create_auto_job(s)
    if job is None:
        return {"ran": False, "reason": "manual_active_or_empty"}

    batch = max(1, int(s.auto_recheck_batch or 25))
    deadline = _time.monotonic() + max_seconds
    processed = 0
    while processed < batch and _time.monotonic() < deadline:
        before = job.processed
        job = run_step(job)
        if job.status != LeadCheckJob.Status.RUNNING:
            break
        if job.processed > before:
            processed += 1
        else:
            # throttle RPM — чекаємо інтервал, потім знімаємо throttle, щоб
            # наступний крок пройшов (cron сам обмежує частоту проходів).
            wait = 1.0
            if job.next_step_not_before:
                wait = (job.next_step_not_before - timezone.now()).total_seconds()
            sleeper(min(max(wait, 0.0), 15))
            LeadCheckJob.objects.filter(id=job.id).update(next_step_not_before=None)
            job.refresh_from_db()
        if not checker_can_run():
            break
    return {"ran": True, "processed": processed, "job_id": job.id, "status": job.status}
