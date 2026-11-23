"""Print the CargoFlow deployment checklist, without exposing secrets."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from system_center.views import readiness


class Command(BaseCommand):
    help = "Review CargoFlow security settings (use --strict before deployment)."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true", help="Exit nonzero if readiness checks are incomplete")

    def handle(self, *args, **options):
        self.stdout.write("CARGOFLOW DEPLOYMENT SETTINGS REVIEW")
        self.stdout.write("Development mode: " + ("YES" if settings.DEBUG else "NO"))
        failed = []
        for label, configured, guidance in readiness():
            self.stdout.write(f"{'PASS' if configured else 'REVIEW'}: {label}")
            if not configured:
                failed.append(label)
        self.stdout.write("\nNo secret values or customer information are shown.")
        self.stdout.write("This checks a subset of settings, not end-to-end security or a deployment certification.")
        if failed and options["strict"]:
            raise CommandError("Deployment review incomplete: " + ", ".join(failed))
        if failed:
            self.stdout.write(self.style.WARNING(f"Review {len(failed)} item(s) before production deployment."))
        else:
            self.stdout.write(self.style.SUCCESS("All selected settings checks passed; broader review still required."))
