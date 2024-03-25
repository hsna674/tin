# Generated by Django 3.2.21 on 2023-12-06 18:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0013_auto_20230709_2221'),
        ('assignments', '0025_assignment_last_action_output'),
    ]

    operations = [
        migrations.CreateModel(
            name='FileAction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('command', models.CharField(max_length=1024)),
                ('match_type', models.CharField(blank=True, choices=[('S', 'Start with'), ('E', 'End with'), ('C', 'Contain')], max_length=1, null=True)),
                ('match_value', models.CharField(blank=True, max_length=100, null=True)),
                ('case_sensitive_match', models.BooleanField(default=False)),
                ('is_sandboxed', models.BooleanField(default=True)),
                ('courses', models.ManyToManyField(related_name='file_actions', to='courses.Course')),
            ],
        ),
    ]