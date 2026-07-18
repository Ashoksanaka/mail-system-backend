import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def backfill_sender_emails(apps, schema_editor):
    ClerkIdentity = apps.get_model("accounts", "ClerkIdentity")
    UserSmtpCredential = apps.get_model("accounts", "UserSmtpCredential")
    for identity in ClerkIdentity.objects.exclude(email="").iterator():
        UserSmtpCredential.objects.get_or_create(
            user_id=identity.user_id,
            defaults={"sender_email": identity.email},
        )


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserSmtpCredential",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "sender_email",
                    models.EmailField(
                        blank=True,
                        default="",
                        help_text="Immutable sender address from Clerk signup",
                        max_length=254,
                    ),
                ),
                (
                    "app_password_encrypted",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Fernet-encrypted Gmail app password",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="smtp_credential",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "User SMTP Credential",
                "verbose_name_plural": "User SMTP Credentials",
            },
        ),
        migrations.RunPython(backfill_sender_emails, migrations.RunPython.noop),
    ]
