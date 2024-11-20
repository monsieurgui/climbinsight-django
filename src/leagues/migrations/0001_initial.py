# Generated by Django 5.1.3 on 2024-11-19 23:24

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
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
                ('governing_body', models.CharField(blank=True, max_length=255, verbose_name='Governing Body')),
                ('sanctioning_body', models.CharField(blank=True, max_length=255, verbose_name='Sanctioning Body')),
                ('seasonal_statistics', models.JSONField(default=dict, verbose_name='Seasonal Statistics')),
                ('historical_records', models.JSONField(default=dict, verbose_name='Historical Records')),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('active', 'Active'), ('completed', 'Completed'), ('archived', 'Archived')], default='draft', max_length=20, verbose_name='Status')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('athletes', models.ManyToManyField(blank=True, related_name='participating_leagues', to=settings.AUTH_USER_MODEL, verbose_name='Athletes')),
                ('officials', models.ManyToManyField(blank=True, related_name='officiating_leagues', to=settings.AUTH_USER_MODEL, verbose_name='Officials')),
                ('technical_delegates', models.ManyToManyField(blank=True, related_name='technical_delegate_leagues', to=settings.AUTH_USER_MODEL, verbose_name='Technical Delegates')),
            ],
            options={
                'verbose_name': 'League',
                'verbose_name_plural': 'Leagues',
                'ordering': ['-start_date'],
            },
        ),
    ]
