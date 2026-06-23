from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='environment',
            name='publisher',
            field=models.TextField(blank=True, default='', null=True),
        ),
    ]
