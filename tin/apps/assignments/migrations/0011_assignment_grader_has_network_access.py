# Generated by Django 2.2.5 on 2019-09-22 12:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assignments', '0010_auto_20190920_1926'),
    ]

    operations = [
        migrations.AddField(
            model_name='assignment',
            name='grader_has_network_access',
            field=models.BooleanField(default=False),
        ),
    ]