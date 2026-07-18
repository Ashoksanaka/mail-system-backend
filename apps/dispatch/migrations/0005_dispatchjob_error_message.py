from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dispatch", "0004_dispatchjob_owner_and_cleanup"),
    ]

    operations = [
        migrations.AddField(
            model_name="dispatchjob",
            name="error_message",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Top-level failure reason when the job fails before/during send",
            ),
        ),
    ]
