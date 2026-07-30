from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0113_igpollcursor_poll_state"),
    ]

    operations = [
        migrations.AddField(
            model_name="instagrambotsettings",
            name="link_send_blocked_until",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="instagrambotsettings",
            name="link_send_last_error_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="instagrambotsettings",
            name="link_send_last_fbtrace_id",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
    ]
