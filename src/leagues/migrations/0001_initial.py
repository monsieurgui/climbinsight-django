# Generated by Django 5.1.3 on 2024-11-11 03:49

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='League',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Name')),
                ('start_date', models.DateField(verbose_name='Start Date')),
                ('end_date', models.DateField(verbose_name='End Date')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('categories', models.JSONField(default=list, verbose_name='Categories')),
                ('ranking_system', models.JSONField(default=dict, verbose_name='Ranking System')),
                ('qualification_criteria', models.JSONField(default=dict, verbose_name='Qualification Criteria')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'League',
                'verbose_name_plural': 'Leagues',
                'ordering': ['-start_date'],
            },
        ),
    ]
