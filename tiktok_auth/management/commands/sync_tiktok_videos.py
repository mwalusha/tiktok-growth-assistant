import logging

from django.core.management.base import BaseCommand, CommandError

from tiktok_auth.models import TikTokAccount
from tiktok_auth.services import TikTokAPIError
from tiktok_auth.sync import sync_tiktok_performance


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Synchronize profile stats and videos for every TikTok account."

    def handle(self, *args, **options):
        accounts = TikTokAccount.objects.order_by("pk")
        account_count = accounts.count()
        videos_created = 0
        videos_updated = 0
        failures = []

        self.stdout.write(
            f"Synchronizing {account_count} TikTok account(s)."
        )

        for account in accounts.iterator():
            try:
                result = sync_tiktok_performance(account)
            except TikTokAPIError as exc:
                failures.append(f"{account.pk}: {exc}")
                logger.exception(
                    "TikTok sync failed for account %s.",
                    account.pk,
                )
                self.stderr.write(
                    self.style.ERROR(
                        f"Account {account.pk} failed: {exc}"
                    )
                )
                continue
            except Exception as exc:
                failures.append(f"{account.pk}: unexpected error")
                logger.exception(
                    "Unexpected TikTok sync failure for account %s.",
                    account.pk,
                )
                self.stderr.write(
                    self.style.ERROR(
                        f"Account {account.pk} failed unexpectedly: {exc}"
                    )
                )
                continue

            videos_created += result["videos_created"]
            videos_updated += result["videos_updated"]
            self.stdout.write(
                self.style.SUCCESS(
                    f"Account {account.pk}: "
                    f"{result['videos_created']} created, "
                    f"{result['videos_updated']} updated."
                )
            )

        if failures:
            raise CommandError(
                f"{len(failures)} of {account_count} account sync(s) failed."
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Sync complete: "
                f"{videos_created} video(s) created, "
                f"{videos_updated} updated."
            )
        )
