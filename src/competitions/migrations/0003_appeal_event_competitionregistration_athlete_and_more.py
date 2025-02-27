# Generated by Django 5.1.6 on 2025-02-14 21:53

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('competitions', '0002_competitionregistration_competitionresult_and_more'),
        ('events', '0001_initial'),
        ('leagues', '0004_category_alter_league_options_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='appeal',
            name='event',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='events.event'),
        ),
        migrations.AddField(
            model_name='competitionregistration',
            name='athlete',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='competitionregistration',
            name='category',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='leagues.category'),
        ),
        migrations.AddField(
            model_name='competitionregistration',
            name='competition',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='competitions.competition'),
        ),
        migrations.AddField(
            model_name='competition',
            name='athletes',
            field=models.ManyToManyField(related_name='competitions', through='competitions.CompetitionRegistration', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='competitionresult',
            name='athlete',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='competitionresult',
            name='category',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='leagues.category'),
        ),
        migrations.AddField(
            model_name='competitionresult',
            name='competition',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='results', to='competitions.competition'),
        ),
        migrations.AlterUniqueTogether(
            name='competitionregistration',
            unique_together={('competition', 'athlete', 'category')},
        ),
        migrations.AlterUniqueTogether(
            name='competitionresult',
            unique_together={('competition', 'athlete', 'category')},
        ),
    ]
