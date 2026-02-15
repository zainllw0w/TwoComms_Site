from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from dtf.minify_assets import build_dtf_minified_assets, summarize_minify_results


class Command(BaseCommand):
    help = "Minify DTF static assets (dtf.css, dtf.js, effects-bundle.js)."

    def handle(self, *args, **options):
        base_dir = settings.BASE_DIR
        try:
            results = build_dtf_minified_assets(base_dir)
        except Exception as exc:  # pragma: no cover
            raise CommandError(f"DTF minification failed: {exc}") from exc

        summary = summarize_minify_results(results)
        self.stdout.write(
            self.style.SUCCESS(
                "DTF assets minified: "
                f"{summary['files_total']} files, "
                f"{summary['files_written']} updated, "
                f"saved {summary['saved_bytes']} bytes"
            )
        )
