import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def delete_legacy_application_data(apps, schema_editor):
    """Remove unowned historical data before enforcing ownership."""
    DispatchLog = apps.get_model("dispatch", "DispatchLog")
    DispatchJob = apps.get_model("dispatch", "DispatchJob")
    EmailTemplate = apps.get_model("templates_manager", "EmailTemplate")
    DispatchLog.objects.all().delete()
    DispatchJob.objects.all().delete()
    EmailTemplate.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("templates_manager", "0003_emailtemplate_attachment_names_and_more"),
        ("dispatch", "0003_alter_dispatchjob_template"),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            delete_legacy_application_data,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="emailtemplate",
            name="name",
            field=models.CharField(
                db_index=True,
                help_text="Template name (unique per owner)",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="emailtemplate",
            name="owner",
            field=models.ForeignKey(
                help_text="Clerk-authenticated user who owns this template",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="email_templates",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="emailtemplate",
            constraint=models.UniqueConstraint(
                fields=("owner", "name"),
                name="uniq_emailtemplate_owner_name",
            ),
        ),
    ]
