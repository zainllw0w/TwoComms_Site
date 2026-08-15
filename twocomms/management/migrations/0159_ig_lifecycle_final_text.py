from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("management", "0158_ig_ugc_intelligence"),
    ]

    operations = [
        migrations.AddField(
            model_name="iglifecycleevent",
            name="final_text",
            field=models.TextField(blank=True, default=""),
        ),
    ]
