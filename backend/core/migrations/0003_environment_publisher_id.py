from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_environment_publisher'),
    ]

    operations = [
        migrations.AddField(
            model_name='environment',
            name='publisher_id',
            field=models.TextField(blank=True, default='', null=True),
        ),
    ]
