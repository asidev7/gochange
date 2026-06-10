"""Attribue un account_code unique aux comptes existants."""
import secrets

from django.db import migrations

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def gen_code(existing):
    while True:
        code = "GC-" + "".join(secrets.choice(ALPHABET) for _ in range(6))
        if code not in existing:
            existing.add(code)
            return code


def backfill(apps, schema_editor):
    User = apps.get_model("accounts", "CustomUser")
    existing = set(
        User.objects.exclude(account_code__isnull=True).values_list("account_code", flat=True)
    )
    for user in User.objects.filter(account_code__isnull=True):
        user.account_code = gen_code(existing)
        user.save(update_fields=["account_code"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_sitesettings_customuser_account_code")]
    operations = [migrations.RunPython(backfill, noop)]
