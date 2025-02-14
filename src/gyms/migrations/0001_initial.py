# Generated by Django 5.1.6 on 2025-02-14 21:53

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Gym',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='name')),
                ('description', models.TextField(blank=True, verbose_name='description')),
                ('address', models.JSONField(default=dict, verbose_name='address')),
                ('coordinates', models.JSONField(default=dict, verbose_name='coordinates')),
                ('capacity', models.JSONField(default=dict, verbose_name='capacity')),
                ('facilities', models.JSONField(default=dict, verbose_name='facilities')),
                ('equipment', models.JSONField(default=dict, verbose_name='equipment inventory')),
                ('safety_certification', models.JSONField(default=dict, verbose_name='safety certification')),
                ('insurance_info', models.JSONField(default=dict, verbose_name='insurance information')),
                ('emergency_contacts', models.JSONField(default=dict, verbose_name='emergency contacts')),
                ('operating_hours', models.JSONField(default=dict, verbose_name='operating hours')),
                ('contact_info', models.JSONField(default=dict, verbose_name='contact information')),
                ('is_active', models.BooleanField(default=True, verbose_name='active')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated at')),
                ('owners', models.ManyToManyField(limit_choices_to={'roles__contains': ['GYM_OWNER']}, related_name='owned_gyms', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'gym',
                'verbose_name_plural': 'gyms',
            },
        ),
        migrations.CreateModel(
            name='GymMembership',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('membership_type', models.CharField(max_length=50, verbose_name='membership type')),
                ('start_date', models.DateField(verbose_name='start date')),
                ('end_date', models.DateField(blank=True, null=True, verbose_name='end date')),
                ('payment_status', models.CharField(max_length=20, verbose_name='payment status')),
                ('is_active', models.BooleanField(default=True, verbose_name='active')),
                ('access_card', models.CharField(blank=True, max_length=50, verbose_name='access card number')),
                ('athlete', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('gym', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='gyms.gym')),
            ],
            options={
                'verbose_name': 'gym membership',
                'verbose_name_plural': 'gym memberships',
                'unique_together': {('gym', 'athlete')},
            },
        ),
        migrations.AddField(
            model_name='gym',
            name='athletes',
            field=models.ManyToManyField(related_name='member_gyms', through='gyms.GymMembership', to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name='GymStaff',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('position', models.CharField(max_length=100, verbose_name='position')),
                ('responsibilities', models.JSONField(verbose_name='responsibilities')),
                ('schedule', models.JSONField(verbose_name='work schedule')),
                ('is_active', models.BooleanField(default=True, verbose_name='active')),
                ('start_date', models.DateField(verbose_name='start date')),
                ('end_date', models.DateField(blank=True, null=True, verbose_name='end date')),
                ('gym', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gym_staff', to='gyms.gym')),
                ('staff_member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'gym staff',
                'verbose_name_plural': 'gym staff',
                'unique_together': {('gym', 'staff_member')},
            },
        ),
        migrations.AddField(
            model_name='gym',
            name='staff',
            field=models.ManyToManyField(related_name='staffed_gyms', through='gyms.GymStaff', to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name='MaintenanceLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('maintenance_type', models.CharField(max_length=100, verbose_name='maintenance type')),
                ('description', models.TextField(verbose_name='description')),
                ('area_affected', models.JSONField(verbose_name='affected area')),
                ('equipment_used', models.JSONField(blank=True, null=True, verbose_name='equipment used')),
                ('date_performed', models.DateTimeField(verbose_name='date performed')),
                ('duration', models.DurationField(verbose_name='duration')),
                ('next_maintenance', models.DateField(blank=True, null=True, verbose_name='next maintenance date')),
                ('gym', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='maintenance_logs', to='gyms.gym')),
                ('performed_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'maintenance log',
                'verbose_name_plural': 'maintenance logs',
                'ordering': ['-date_performed'],
            },
        ),
        migrations.CreateModel(
            name='Route',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='name')),
                ('grade', models.CharField(max_length=10, verbose_name='grade')),
                ('color', models.CharField(max_length=50, verbose_name='color')),
                ('location', models.JSONField(verbose_name='location in gym')),
                ('description', models.TextField(blank=True, verbose_name='description')),
                ('set_date', models.DateField(verbose_name='set date')),
                ('removal_date', models.DateField(blank=True, null=True, verbose_name='removal date')),
                ('is_active', models.BooleanField(default=True, verbose_name='active')),
                ('gym', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='routes', to='gyms.gym')),
                ('setter', models.ForeignKey(limit_choices_to={'roles__contains': ['ROUTE_SETTER']}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='set_routes', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'route',
                'verbose_name_plural': 'routes',
                'ordering': ['-set_date'],
            },
        ),
    ]
