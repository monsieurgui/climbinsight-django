from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from leagues.models import League, Category

# Create your models here.

class Competition(models.Model):
    """Main competition model."""
    
    name = models.CharField(_('name'), max_length=255)
    description = models.TextField(_('description'))
    league = models.ForeignKey(League, on_delete=models.CASCADE, related_name='competitions')
    
    # Dates and location
    start_date = models.DateTimeField(_('start date'), null=True)
    end_date = models.DateTimeField(_('end date'), null=True)
    location = models.JSONField(_('location'), default=dict)  # Structured location data
    
    # Relationships
    categories = models.ManyToManyField(Category, related_name='competitions')
    athletes = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='CompetitionRegistration',
        related_name='competitions'
    )
    officials = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='officiating_competitions',
        limit_choices_to={'roles__contains': ['OFFICIAL']}
    )
    technical_delegate = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='delegated_competitions',
        limit_choices_to={'roles__contains': ['TECH_DELEGATE']}
    )
    route_setters = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='route_setting_competitions',
        limit_choices_to={'roles__contains': ['ROUTE_SETTER']}
    )
    medical_staff = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='medical_competitions',
        limit_choices_to={'roles__contains': ['MEDICAL_STAFF']}
    )
    
    # Configuration
    ruleset = models.JSONField(_('ruleset configuration'), default=dict)
    scoring_system = models.JSONField(_('scoring system'), default=dict)
    registration_deadline = models.DateTimeField(_('registration deadline'), null=True)
    
    # Safety and procedures
    safety_protocols = models.JSONField(_('safety protocols'), default=dict)
    emergency_procedures = models.JSONField(_('emergency procedures'), default=dict)
    isolation_zones = models.JSONField(_('isolation zones'), null=True, blank=True)
    warmup_areas = models.JSONField(_('warmup areas'), default=dict)
    
    # Equipment and resources
    equipment_inventory = models.JSONField(_('equipment inventory'), null=True, blank=True)
    resource_requirements = models.JSONField(_('resource requirements'), null=True, blank=True)
    
    # Status and metadata
    status = models.CharField(_('status'), max_length=20, default='draft')
    is_active = models.BooleanField(_('active'), default=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('competition')
        verbose_name_plural = _('competitions')
        ordering = ['start_date']
        
    def __str__(self):
        return self.name


class CompetitionRegistration(models.Model):
    """Registration of athletes for competitions."""
    
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE)
    athlete = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    
    # Registration status and details
    status = models.CharField(_('status'), max_length=20, default='pending')
    registration_date = models.DateTimeField(_('registration date'), auto_now_add=True)
    check_in_time = models.DateTimeField(_('check in time'), null=True, blank=True)
    bib_number = models.CharField(_('bib number'), max_length=10, null=True, blank=True)
    
    # Waivers and requirements
    waiver_signed = models.BooleanField(_('waiver signed'), default=False)
    medical_clearance = models.BooleanField(_('medical clearance'), default=False)
    requirements_met = models.JSONField(_('requirements met'), default=dict)
    
    class Meta:
        verbose_name = _('competition registration')
        verbose_name_plural = _('competition registrations')
        unique_together = ['competition', 'athlete', 'category']


class CompetitionResult(models.Model):
    """Results for athletes in competitions."""
    
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name='results')
    athlete = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    
    # Results
    ranking = models.IntegerField(_('ranking'))
    score = models.JSONField(_('score details'))
    attempts = models.JSONField(_('attempts'), default=list)
    disqualified = models.BooleanField(_('disqualified'), default=False)
    disqualification_reason = models.TextField(_('disqualification reason'), blank=True)
    
    class Meta:
        verbose_name = _('competition result')
        verbose_name_plural = _('competition results')
        unique_together = ['competition', 'athlete', 'category']
        ordering = ['category', 'ranking']


class Appeal(models.Model):
    """Appeals made during competitions."""
    
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name='appeals')
    athlete = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event = models.ForeignKey('events.Event', on_delete=models.CASCADE)
    
    # Appeal details
    reason = models.TextField(_('appeal reason'))
    evidence = models.JSONField(_('evidence'), null=True, blank=True)
    submitted_at = models.DateTimeField(_('submitted at'), auto_now_add=True)
    
    # Decision
    status = models.CharField(_('status'), max_length=20, default='pending')
    decision = models.TextField(_('decision'), blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='appeal_decisions'
    )
    decided_at = models.DateTimeField(_('decided at'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('appeal')
        verbose_name_plural = _('appeals')
        ordering = ['-submitted_at']
