# Generated by Django 5.1.3 on 2024-11-19 22:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_create_default_roles'),
    ]

    operations = [
        migrations.CreateModel(
            name='Profile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('official_roles', models.JSONField(default=list, help_text='List of official roles this user can perform', verbose_name='Official Roles')),
                ('official_certifications', models.JSONField(default=list, help_text='List of certifications held by the official', verbose_name='Official Certifications')),
                ('athlete_categories', models.JSONField(default=list, help_text='Categories in which this athlete competes', verbose_name='Athlete Categories')),
                ('competition_history', models.JSONField(blank=True, default=dict, help_text='Historical record of competition participation and results', verbose_name='Competition History')),
            ],
            options={
                'verbose_name': 'Profile',
                'verbose_name_plural': 'Profiles',
            },
        ),
    ]
