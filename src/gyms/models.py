from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings


class Gym(models.Model):
    """Main gym model."""
    
    name = models.CharField(_('name'), max_length=255)
    description = models.TextField(_('description'), blank=True)
    
    # Location
    address = models.JSONField(_('address'), default=dict)
    coordinates = models.JSONField(_('coordinates'), default=dict)  # Latitude and longitude
    
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
    capacity = models.JSONField(_('capacity'), default=dict)  # Different capacity limits
    facilities = models.JSONField(_('facilities'), default=dict)  # Available facilities
    equipment = models.JSONField(_('equipment inventory'), default=dict)
    
    # Safety and certification
    safety_certification = models.JSONField(_('safety certification'), default=dict)
    insurance_info = models.JSONField(_('insurance information'), default=dict)
    emergency_contacts = models.JSONField(_('emergency contacts'), default=dict)
    
    # Operating information
    operating_hours = models.JSONField(_('operating hours'), default=dict)
    contact_info = models.JSONField(_('contact information'), default=dict)
    
    # Status and metadata
    is_active = models.BooleanField(_('active'), default=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('gym')
        verbose_name_plural = _('gyms')
        
    def __str__(self):
        return self.name


class GymStaff(models.Model):
    """Staff members of a gym."""
    
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, related_name='gym_staff')
    staff_member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    # Role information
    position = models.CharField(_('position'), max_length=100)
    responsibilities = models.JSONField(_('responsibilities'))
    schedule = models.JSONField(_('work schedule'))
    
    # Status
    is_active = models.BooleanField(_('active'), default=True)
    start_date = models.DateField(_('start date'))
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
    membership_type = models.CharField(_('membership type'), max_length=50)
    start_date = models.DateField(_('start date'))
    end_date = models.DateField(_('end date'), null=True, blank=True)
    payment_status = models.CharField(_('payment status'), max_length=20)
    
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
    grade = models.CharField(_('grade'), max_length=10)
    color = models.CharField(_('color'), max_length=50)
    location = models.JSONField(_('location in gym'))
    description = models.TextField(_('description'), blank=True)
    
    # Setting information
    setter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='set_routes',
        limit_choices_to={'roles__contains': ['ROUTE_SETTER']}
    )
    set_date = models.DateField(_('set date'))
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
    maintenance_type = models.CharField(_('maintenance type'), max_length=100)
    description = models.TextField(_('description'))
    area_affected = models.JSONField(_('affected area'))
    equipment_used = models.JSONField(_('equipment used'), null=True, blank=True)
    
    # Timing
    date_performed = models.DateTimeField(_('date performed'))
    duration = models.DurationField(_('duration'))
    next_maintenance = models.DateField(_('next maintenance date'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('maintenance log')
        verbose_name_plural = _('maintenance logs')
        ordering = ['-date_performed']
