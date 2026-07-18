import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("dispatch", "0003_alter_dispatchjob_template"),
        ("templates_manager", "0004_emailtemplate_owner_and_cleanup"),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="dispatchjob",
            name="owner",
            field=models.ForeignKey(
                help_text="Clerk-authenticated user who owns this job",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="dispatch_jobs",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddIndex(
            model_name="dispatchjob",
            index=models.Index(
                fields=["owner", "status"],
                name="dispatch_di_owner_i_7b6f0a_idx",
            ),
        ),
    ]
