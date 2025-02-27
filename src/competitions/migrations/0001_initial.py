# Generated by Django 5.1.3 on 2024-11-19 23:24

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('leagues', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Competition',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Name')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('location', models.CharField(max_length=255, verbose_name='Location')),
                ('start_datetime', models.DateTimeField(verbose_name='Start Date and Time')),
                ('end_datetime', models.DateTimeField(verbose_name='End Date and Time')),
                ('ruleset', models.CharField(choices=[('standard', 'Standard'), ('modified', 'Modified'), ('youth', 'Youth')], max_length=50, verbose_name='Ruleset')),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('published', 'Published'), ('in_progress', 'In Progress'), ('completed', 'Completed'), ('cancelled', 'Cancelled')], default='draft', max_length=20, verbose_name='Status')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('league', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='competitions', to='leagues.league')),
                ('technical_delegate', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='competitions_as_delegate', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Competition',
                'verbose_name_plural': 'Competitions',
                'ordering': ['start_datetime'],
            },
        ),
    ]
