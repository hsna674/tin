# Generated by Django 2.2.3 on 2019-07-30 19:36

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('assignments', '0005_assignment_requested_num_containers'),
        ('submissions', '0009_auto_20190725_1210'),
    ]

    operations = [
        migrations.CreateModel(
            name='Container',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=40, unique=True)),
                ('last_upgrade', models.DateTimeField()),
                ('assignment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='containers', to='assignments.Assignment')),
            ],
        ),
        migrations.CreateModel(
            name='ContainerTask',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('container', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='task', to='containers.Container')),
                ('submission', models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='container_task', to='submissions.Submission')),
            ],
        ),
        migrations.CreateModel(
            name='ContainerPackage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('package_type', models.CharField(choices=[('apt', 'Apt'), ('pip', 'Pip')], max_length=6)),
                ('install_globally', models.BooleanField(default=False)),
                ('assignments', models.ManyToManyField(blank=True, null=True, related_name='packages', to='assignments.Assignment')),
            ],
        ),
        migrations.AddField(
            model_name='container',
            name='installed_packages',
            field=models.ManyToManyField(related_name='containers', to='containers.ContainerPackage'),
        ),
    ]