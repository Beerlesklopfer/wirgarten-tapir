import os
import sys
import traceback
from typing import Literal

from django.core.management import BaseCommand
from django.db import transaction
from icecream import ic

from tapir.accounts.models import EmailChangeRequest
from tapir.accounts.services.keycloak_user_delete_service import (
    KeycloakUserDeleteService,
)
from tapir.deliveries.models import Joker
from tapir.payments.config import PAYMENT_TYPE_COOP_SHARES
from tapir.payments.models import MemberCredit
from tapir.solidarity_contribution.models import SolidarityContribution
from tapir.utils.config import (
    MEMBER_IMPORT_STATUS_SKIPPED,
    MEMBER_IMPORT_STATUS_CREATED,
    MEMBER_IMPORT_STATUS_UPDATED,
)
from tapir.utils.exceptions import DryRunException
from tapir.utils.services.member_importer import MemberImporter
from tapir.utils.services.share_importer import ShareImporter
from tapir.utils.services.subscription_importer import SubscriptionImporter
from tapir.utils.services.tabular_file_reader import TabularFileReader
from tapir.wirgarten.models import (
    Member,
    Subscription,
    CoopShareTransaction,
    MandateReference,
    MemberPickupLocation,
    Payment,
    LogEntry,
    QuestionaireCancellationReasonResponse,
    QuestionaireTrafficSourceResponse,
    WaitingListEntry,
    TransferCoopSharesLogEntry,
    SubscriptionChangeLogEntry,
    PaymentTransaction,
)


class Command(BaseCommand):
    help = "Imports data from CSV files into the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--type", nargs=1, choices=["members", "shares", "subscriptions"]
        )
        parser.add_argument("--file", nargs=1)
        parser.add_argument("--delete-all", action="store_true")
        parser.add_argument("--reset-all", action="store_true")
        parser.add_argument(
            "--verify-csv",
            action="store_true",
            help=(
                "Read the CSV, normalize headers, print raw/cleaned headers and the first row, then exit "
                "(no database writes)."
            ),
        )
        parser.add_argument(
            "--update",
            nargs=1,
            choices=["yes", "no"],
            default=["no"],
            help="Update existing records if differences are found (yes/no). Default: no.",
        )

        parser.add_argument(
            "--dry-run", action="store_true", help="If enabled, no change will be saved"
        )

        parser.add_argument(
            "--stacktrace",
            action="store_true",
            help="If enabled, will print the stacktrace for all errors. Otherwise, only a short summary will be printed",
        )

    def handle(self, *args, **options):
        # Helper functions

        if options["reset_all"]:
            SolidarityContribution.objects.all().delete()
            SubscriptionChangeLogEntry.objects.all().delete()
            TransferCoopSharesLogEntry.objects.all().delete()
            CoopShareTransaction.objects.all().delete()
            Subscription.objects.all().delete()
            Payment.objects.all().delete()
            MandateReference.objects.all().delete()
            MemberPickupLocation.objects.all().delete()
            LogEntry.objects.all().delete()
            QuestionaireCancellationReasonResponse.objects.all().delete()
            QuestionaireTrafficSourceResponse.objects.all().delete()
            WaitingListEntry.objects.all().delete()
            EmailChangeRequest.objects.all().delete()
            MemberCredit.objects.all().delete()
            Joker.objects.all().delete()
            cache = {}
            for member in Member.objects.all():
                KeycloakUserDeleteService.delete_user_if_exists(
                    user=member, cache=cache
                )
                member.delete()
            return

        # check if type and file params are present
        if (
            not options.get("file")
            or not options["file"][0]
            or not options.get("type")
            or not options["type"][0]
        ):
            self.stderr.write(
                "If not --reset-all is used, parameters --type and --file must be present."
            )
            return

        filepath = options["file"][0]
        import_type = options["type"][0]
        delete_all = options["delete_all"]
        dry_run = options.get("dry_run", False)
        print_stacktrace = options.get("stacktrace", False)
        update_existing = options.get("update")[0] == "yes"

        # Excel (.xlsx) or CSV; header names are cleaned of invisible characters
        with open(filepath, "rb") as f:
            data = TabularFileReader.read(f, filepath)
        reader = iter(data.rows)

        # Optional verification mode: show what the importer sees without touching the DB
        if options.get("verify_csv"):
            self.verify_csv(data.headers, reader)
            return

        try:
            with transaction.atomic():
                if delete_all:
                    if import_type == "members":
                        SolidarityContribution.objects.all().delete()
                        SubscriptionChangeLogEntry.objects.all().delete()
                        TransferCoopSharesLogEntry.objects.all().delete()
                        CoopShareTransaction.objects.all().delete()
                        Subscription.objects.all().delete()
                        Payment.objects.all().delete()
                        MandateReference.objects.all().delete()
                        MemberPickupLocation.objects.all().delete()
                        LogEntry.objects.all().delete()
                        QuestionaireCancellationReasonResponse.objects.all().delete()
                        QuestionaireTrafficSourceResponse.objects.all().delete()
                        WaitingListEntry.objects.all().delete()
                        EmailChangeRequest.objects.all().delete()
                        MemberCredit.objects.all().delete()
                        Joker.objects.all().delete()
                        cache = {}
                        for member in Member.objects.all():
                            KeycloakUserDeleteService.delete_user_if_exists(
                                user=member, cache=cache
                            )
                            member.delete()

                    if import_type == "shares":
                        TransferCoopSharesLogEntry.objects.all().delete()
                        CoopShareTransaction.objects.all().delete()

                    if import_type == "subscriptions":
                        SubscriptionChangeLogEntry.objects.all().delete()
                        Subscription.objects.all().delete()
                        PaymentTransaction.objects.exclude(
                            type=PAYMENT_TYPE_COOP_SHARES
                        ).delete()
                        Payment.objects.exclude(type=PAYMENT_TYPE_COOP_SHARES).delete()

                self.import_generic(
                    reader=reader,
                    update_existing=update_existing,
                    import_type=import_type,
                    print_stacktrace=print_stacktrace,
                )
                if dry_run:
                    raise DryRunException()
        except DryRunException:
            pass

    def verify_csv(self, cleaned_headers: list[str], reader):
        self.stdout.write(f"Cleaned headers: {cleaned_headers}")
        try:
            first_row = next(reader)
        except StopIteration:
            self.stdout.write("CSV contains only a header row, no data rows.")
            return
        self.stdout.write(f"First row (as dict with cleaned headers): {first_row}")

    def print_results(self, created: int, updated: int, skipped: int):
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created: {created}, Updated: {updated}, Skipped: {skipped}"
            )
        )

    def import_generic(
        self,
        reader,
        update_existing: bool,
        import_type: Literal["members", "shares", "subscriptions"],
        print_stacktrace: bool,
    ):
        skipped = 0
        created = 0
        updated = 0

        for row_index, row in enumerate(reader):
            try:
                match import_type:
                    case "members":
                        method = MemberImporter.import_member
                    case "shares":
                        method = ShareImporter.import_shares_single_member
                    case "subscriptions":
                        method = SubscriptionImporter.import_subscription

                with transaction.atomic():
                    import_status = method(row=row, update_existing=update_existing)

                if import_status == MEMBER_IMPORT_STATUS_SKIPPED:
                    skipped += 1
                if import_status == MEMBER_IMPORT_STATUS_CREATED:
                    created += 1
                if import_status == MEMBER_IMPORT_STATUS_UPDATED:
                    updated += 1

            except Exception as exception:
                self.stderr.write(
                    f"Error while importing row with internal index {row_index} (should be line {row_index+2} in the file), import type: {import_type}"
                )
                self.print_exception_details(exception, print_stacktrace)
                self.stderr.write(ic.format(row))
                skipped += 1
                continue

        self.print_results(created=created, updated=updated, skipped=skipped)

    def print_exception_details(self, exception, print_stacktrace: bool):
        _, _, exception_traceback = sys.exc_info()
        exception_filename = os.path.split(
            exception_traceback.tb_frame.f_code.co_filename
        )[1]
        exception_line_number = exception_traceback.tb_lineno
        self.stderr.write(f"{exception}, {exception_filename}:L{exception_line_number}")
        if print_stacktrace:
            self.stderr.write(traceback.format_exc())
