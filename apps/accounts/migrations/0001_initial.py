import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ClerkIdentity",
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
                    "clerk_user_id",
                    models.CharField(
                        db_index=True,
                        help_text="Clerk user id (JWT sub), e.g. user_...",
                        max_length=255,
                        unique=True,
                    ),
                ),
                ("email", models.EmailField(blank=True, default="", max_length=254)),
                (
                    "first_name",
                    models.CharField(blank=True, default="", max_length=150),
                ),
                (
                    "last_name",
                    models.CharField(blank=True, default="", max_length=150),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="clerk_identity",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Clerk Identity",
                "verbose_name_plural": "Clerk Identities",
            },
        ),
    ]
