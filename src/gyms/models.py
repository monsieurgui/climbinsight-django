from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings


class Gym(models.Model):
    """Main gym model."""
    
    name = models.CharField(max_length=255)
    address = models.TextField(null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)
    contact_info = models.JSONField(default=dict)
    facilities = models.JSONField(null=True, blank=True)
    operating_hours = models.JSONField(null=True, blank=True)
    climbing_areas = models.JSONField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Location
    coordinates = models.JSONField(_('coordinates'), default=dict)
    
    # Relationships
    owners = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='owned_gyms',
        limit_choices_to={'roles__contains': ['GYM_OWNER']}
    )
    staff = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='GymStaff',
        related_name='staffed_gyms'
    )
    athletes = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='GymMembership',
        related_name='member_gyms'
    )
    
    # Facility details
    capacity = models.JSONField(_('capacity'), default=dict)
    equipment = models.JSONField(_('equipment inventory'), default=dict)
    
    # Safety and certification
    safety_certification = models.JSONField(_('safety certification'), default=dict)
    insurance_info = models.JSONField(_('insurance information'), default=dict)
    emergency_contacts = models.JSONField(_('emergency contacts'), default=dict)
    
    def __str__(self):
        return f"{self.name} ({self.city}, {self.country})"

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['city']),
            models.Index(fields=['country']),
            models.Index(fields=['is_active'])
        ]


class GymStaff(models.Model):
    """Staff members of a gym."""
    
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, related_name='gym_staff')
    staff_member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    # Role information
    position = models.CharField(_('position'), max_length=100, null=True, blank=True)
    responsibilities = models.JSONField(_('responsibilities'), default=dict)
    schedule = models.JSONField(_('work schedule'), default=dict)
    
    # Status
    is_active = models.BooleanField(_('active'), default=True)
    start_date = models.DateField(_('start date'), null=True, blank=True)
    end_date = models.DateField(_('end date'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('gym staff')
        verbose_name_plural = _('gym staff')
        unique_together = ['gym', 'staff_member']


class GymMembership(models.Model):
    """Membership of athletes in a gym."""
    
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, related_name='memberships')
    athlete = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    # Membership details
    membership_type = models.CharField(_('membership type'), max_length=50, null=True, blank=True)
    start_date = models.DateField(_('start date'), null=True, blank=True)
    end_date = models.DateField(_('end date'), null=True, blank=True)
    payment_status = models.CharField(_('payment status'), max_length=20, null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(_('active'), default=True)
    access_card = models.CharField(_('access card number'), max_length=50, blank=True)
    
    class Meta:
        verbose_name = _('gym membership')
        verbose_name_plural = _('gym memberships')
        unique_together = ['gym', 'athlete']


class Route(models.Model):
    """Climbing routes in the gym."""
    
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, related_name='routes')
    name = models.CharField(_('name'), max_length=255)
    
    # Route details
    grade = models.CharField(_('grade'), max_length=10, null=True, blank=True)
    color = models.CharField(_('color'), max_length=50, null=True, blank=True)
    location = models.JSONField(_('location in gym'), default=dict)
    description = models.TextField(_('description'), blank=True)
    
    # Setting information
    setter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='set_routes',
        limit_choices_to={'roles__contains': ['ROUTE_SETTER']}
    )
    set_date = models.DateField(_('set date'), null=True, blank=True)
    removal_date = models.DateField(_('removal date'), null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(_('active'), default=True)
    
    class Meta:
        verbose_name = _('route')
        verbose_name_plural = _('routes')
        ordering = ['-set_date']


class MaintenanceLog(models.Model):
    """Maintenance records for the gym."""
    
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, related_name='maintenance_logs')
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    # Maintenance details
    maintenance_type = models.CharField(_('maintenance type'), max_length=100, null=True, blank=True)
    description = models.TextField(_('description'), null=True, blank=True)
    area_affected = models.JSONField(_('affected area'), default=dict)
    equipment_used = models.JSONField(_('equipment used'), null=True, blank=True)
    
    # Timing
    date_performed = models.DateTimeField(_('date performed'), null=True, blank=True)
    duration = models.DurationField(_('duration'), null=True, blank=True)
    next_maintenance = models.DateField(_('next maintenance date'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('maintenance log')
        verbose_name_plural = _('maintenance logs')
        ordering = ['-date_performed']
