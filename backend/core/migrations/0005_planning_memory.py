import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_test_generated_spec_filenames'),
    ]

    operations = [
        migrations.AddField(
            model_name='test',
            name='latest_good_plan',
            field=models.TextField(default=''),
        ),
        migrations.AddField(
            model_name='test',
            name='failed_at_step',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='TestPlanningMemory',
            fields=[
                ('id', models.TextField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('content', models.TextField()),
                ('created_at', models.TextField()),
                ('updated_at', models.TextField()),
                ('deleted_at', models.TextField(blank=True, null=True)),
                ('test', models.ForeignKey(
                    db_column='test_id',
                    on_delete=django.db.models.deletion.RESTRICT,
                    related_name='planning_memories',
                    to='core.test',
                )),
            ],
            options={
                'db_table': 'test_planning_memory',
            },
        ),
    ]
