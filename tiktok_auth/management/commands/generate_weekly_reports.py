import logging

from django.core.management.base import BaseCommand, CommandError

from tiktok_auth.models import TikTokAccount
from tiktok_auth.weekly_reports import generate_weekly_report


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Create the previous week's digest for every TikTok account."

    def handle(self, *args, **options):
        accounts = TikTokAccount.objects.order_by("pk")
        account_count = accounts.count()
        failures = 0

        self.stdout.write(
            f"Generating reports for {account_count} account(s)."
        )

        for account in accounts.iterator():
            try:
                report, created = generate_weekly_report(
                    account
                )
            except Exception as exc:
                failures += 1
                logger.exception(
                    "Weekly report failed for account %s.",
                    account.pk,
                )
                self.stderr.write(
                    self.style.ERROR(
                        f"Account {account.pk} failed: {exc}"
                    )
                )
                continue

            action = "created" if created else "updated"
            self.stdout.write(
                self.style.SUCCESS(
                    f"Account {account.pk}: week of "
                    f"{report.week_start} {action}."
                )
            )

        if failures:
            raise CommandError(
                f"{failures} of {account_count} report(s) failed."
            )

        self.stdout.write(self.style.SUCCESS("Weekly reports complete."))
