# Generated by Django 3.2.24 on 2024-02-20 20:20

from django.db import migrations, models
import django.db.models.deletion
import tin.apps.assignments.models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0013_auto_20230709_2221'),
        ('assignments', '0026_fileaction'),
    ]

    operations = [
        migrations.CreateModel(
            name='MossResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('language', models.CharField(choices=[('c', 'C'), ('cc', 'C++'), ('java', 'Java'), ('ml', 'ML'), ('pascal', 'Pascal'), ('ada', 'Ada'), ('lisp', 'Lisp'), ('scheme', 'Scheme'), ('haskell', 'Haskell'), ('fortran', 'Fortran'), ('ascii', 'ASCII'), ('vhdl', 'VHDL'), ('verilog', 'Verilog'), ('perl', 'Perl'), ('matlab', 'Matlab'), ('python', 'Python'), ('mips', 'MIPS'), ('prolog', 'Prolog'), ('spice', 'Spice'), ('vb', 'Visual Basic'), ('csharp', 'C#'), ('modula2', 'Modula-2'), ('a8086', 'a8086 Assembly'), ('javascript', 'JavaScript'), ('plsql', 'PL/SQL')], default='python', max_length=10)),
                ('base_file', models.FileField(blank=True, null=True, upload_to=tin.apps.assignments.models.moss_base_file_path)),
                ('user_id', models.CharField(max_length=20)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('url', models.URLField(blank=True, null=True)),
                ('status', models.CharField(blank=True, default='', max_length=1024)),
                ('assignment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='moss_results', to='assignments.assignment')),
                ('period', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='moss_results', to='courses.period')),
            ],
        ),
    ]
