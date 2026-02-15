from __future__ import annotations

from django.conf import settings
from django.contrib.staticfiles.management.commands.collectstatic import (
    Command as DjangoCollectStaticCommand,
)
from django.core.management.base import CommandError

from dtf.minify_assets import build_dtf_minified_assets, summarize_minify_results


class Command(DjangoCollectStaticCommand):
    help = (
        "Collect static files and auto-minify DTF bundles "
        "(dtf.css, dtf.js, effects-bundle.js) before collection."
    )

    def handle(self, *args, **options):
        if not options.get("dry_run", False):
            self._run_dtf_minification()
        return super().handle(*args, **options)

    def _run_dtf_minification(self):
        self.stdout.write("Running DTF asset minification before collectstatic...")
        try:
            results = build_dtf_minified_assets(settings.BASE_DIR)
        except Exception as exc:  # pragma: no cover
            raise CommandError(f"DTF minification failed: {exc}") from exc

        summary = summarize_minify_results(results)
        self.stdout.write(
            self.style.SUCCESS(
                "DTF minification complete: "
                f"{summary['files_total']} files, "
                f"{summary['files_written']} updated, "
                f"saved {summary['saved_bytes']} bytes"
            )
        )
