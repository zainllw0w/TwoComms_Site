import json

from django.core.management.base import BaseCommand

from management.models import Client, LeadParsingResult, ManagementLead, normalize_phone


class Command(BaseCommand):
    help = "Dry-run переоцінка історичних parser results, які могли бути пропущені через стару дедуплікацію."

    def add_arguments(self, parser):
        parser.add_argument("--job-id", type=int, help="Обмежити аналіз конкретною сесією парсингу.")
        parser.add_argument("--limit", type=int, default=200, help="Максимум кандидатів у dry-run звіті.")
        parser.add_argument(
            "--scan-limit",
            type=int,
            default=5000,
            help="Максимум історичних записів для перегляду за один dry-run, щоб команда не перевантажувала прод.",
        )
        parser.add_argument("--json", action="store_true", help="Вивести результат у JSON.")

    def handle(self, *args, **options):
        qs = (
            LeadParsingResult.objects.filter(lead__isnull=True)
            .exclude(phone="")
            .filter(
                status__in=[
                    LeadParsingResult.ResultStatus.DUPLICATE,
                    LeadParsingResult.ResultStatus.REJECTED,
                    LeadParsingResult.ResultStatus.ERROR,
                ]
            )
            .only("id", "job_id", "phone", "place_name", "query", "city", "keyword", "status", "reason", "reason_code", "created_at")
            .order_by("-created_at")
        )
        if options.get("job_id"):
            qs = qs.filter(job_id=options["job_id"])

        limit = max(1, int(options.get("limit") or 200))
        scan_limit = max(1, int(options.get("scan_limit") or 5000))
        candidates = []
        seen_phones: set[str] = set()
        scanned_count = 0

        for result in qs.iterator(chunk_size=200):
            scanned_count += 1
            if scanned_count > scan_limit:
                break
            phone_normalized = normalize_phone(result.phone)
            if not phone_normalized or phone_normalized in seen_phones:
                continue
            if Client.objects.filter(phone_normalized=phone_normalized).exists():
                continue
            if ManagementLead.objects.filter(phone_normalized=phone_normalized).exists():
                continue

            seen_phones.add(phone_normalized)
            payload = {
                "result_id": result.id,
                "job_id": result.job_id,
                "phone": phone_normalized,
                "place_name": result.place_name,
                "query": result.query,
                "city": result.city,
                "keyword": result.keyword,
                "status": result.status,
                "reason": result.reason,
                "reason_code": result.reason_code,
                "created_at": result.created_at.isoformat(),
            }
            candidates.append(payload)
            if len(candidates) >= limit:
                break

        summary = {
            "job_id": options.get("job_id"),
            "limit": limit,
            "scan_limit": scan_limit,
            "scanned_count": min(scanned_count, scan_limit),
            "truncated": scanned_count > scan_limit,
            "candidate_count": len(candidates),
            "candidates": candidates,
        }

        if options.get("json"):
            self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2))
            return

        truncated_note = " (scan truncated)" if summary["truncated"] else ""
        self.stdout.write(self.style.SUCCESS(f"Dry-run candidates: {len(candidates)}{truncated_note}"))
        if options.get("job_id"):
            self.stdout.write(f"Job: {options['job_id']}")
        self.stdout.write(f"Scanned: {summary['scanned_count']}/{summary['scan_limit']}")
        for item in candidates:
            self.stdout.write(
                f"- [{item['job_id']}:{item['result_id']}] {item['phone']} | {item['place_name'] or '—'} | "
                f"{item['query'] or '—'} | {item['reason_code'] or item['status']}"
            )
