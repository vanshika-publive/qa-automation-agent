from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_environment_publisher_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='test',
            name='generated_spec_filenames',
            field=models.TextField(default='[]'),
        ),
    ]
