from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='executionstep',
            name='prompt_tokens',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='executionstep',
            name='cached_tokens',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='executionstep',
            name='completion_tokens',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='executionstep',
            name='cost_usd',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
