from django.core.management.base import BaseCommand

from storefront.tasks import check_survey_inactivity_task


class Command(BaseCommand):
    help = "Send partial/updated survey reports for inactive survey sessions."

    def handle(self, *args, **options):
        triggered = check_survey_inactivity_task()
        self.stdout.write(self.style.SUCCESS(f"Triggered {triggered} survey report(s)."))
