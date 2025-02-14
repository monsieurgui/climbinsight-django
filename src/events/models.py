from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from competitions.models import Competition, Category


class Event(models.Model):
    """Main event model."""
    
    class EventTypes(models.TextChoices):
        SCRAMBLE = 'SCRAMBLE', _('Scramble')
        JUDGED_SCRAMBLE = 'JUDGED_SCRAMBLE', _('Judged Scramble')
        QUALIFICATIONS_LEAD = 'QUALIFICATIONS_LEAD', _('Qualifications Lead')
        QUALIFICATIONS_COMBINED = 'QUALIFICATIONS_COMBINED', _('Qualifications Combined')
        SEMIFINALS_5 = 'SEMIFINALS_5', _('Semi-finals 5')
        SEMIFINALS_4 = 'SEMIFINALS_4', _('Semi-finals 4')
        SEMIFINALS_LEAD = 'SEMIFINALS_LEAD', _('Semi-finals Lead')
        SEMIFINALS_COMBINED = 'SEMIFINALS_COMBINED', _('Semi-finals Combined')
        FINALS_4 = 'FINALS_4', _('Finals 4')
        FINALS_5 = 'FINALS_5', _('Finals 5')
        FINALS_LEAD = 'FINALS_LEAD', _('Finals Lead')
        FINALS_COMBINED = 'FINALS_COMBINED', _('Finals Combined')
    
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(_('event type'), max_length=50, choices=EventTypes.choices)
    name = models.CharField(_('name'), max_length=255)
    description = models.TextField(_('description'), blank=True)
    
    # Timing
    start_time = models.DateTimeField(_('start time'), null=True)
    end_time = models.DateTimeField(_('end time'), null=True)
    isolation_start = models.DateTimeField(_('isolation start'), null=True, blank=True)
    isolation_end = models.DateTimeField(_('isolation end'), null=True, blank=True)
    
    # Location and setup
    location = models.JSONField(_('location'), default=dict)  # Specific area within the competition venue
    route_info = models.JSONField(_('route information'), null=True, blank=True)
    
    # Participants
    categories = models.ManyToManyField(Category, related_name='events')
    athletes = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='EventParticipation',
        related_name='events'
    )
    officials = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='officiating_events',
        limit_choices_to={'roles__contains': ['OFFICIAL']}
    )
    
    # Configuration
    starting_order = models.JSONField(_('starting order'), null=True, blank=True)
    scoring_rules = models.JSONField(_('scoring rules'), default=dict)
    safety_requirements = models.JSONField(_('safety requirements'), default=dict)
    
    # Status and metadata
    status = models.CharField(_('status'), max_length=20, default='scheduled')
    is_active = models.BooleanField(_('active'), default=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('event')
        verbose_name_plural = _('events')
        ordering = ['start_time']
        
    def __str__(self):
        return f"{self.name} ({self.get_event_type_display()})"


class EventParticipation(models.Model):
    """Participation of athletes in events."""
    
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    athlete = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    
    # Participation details
    starting_position = models.IntegerField(_('starting position'), null=True, blank=True)
    status = models.CharField(_('status'), max_length=20, default='registered')
    check_in_time = models.DateTimeField(_('check in time'), null=True, blank=True)
    
    # Results tracking
    attempts = models.JSONField(_('attempts'), default=list)
    best_result = models.JSONField(_('best result'), null=True, blank=True)
    final_ranking = models.IntegerField(_('final ranking'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('event participation')
        verbose_name_plural = _('event participations')
        unique_together = ['event', 'athlete', 'category']
        ordering = ['category', 'starting_position']


class EventIncident(models.Model):
    """Incidents that occur during events."""
    
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='incidents')
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='reported_incidents'
    )
    
    # Incident details
    incident_time = models.DateTimeField(_('incident time'))
    incident_type = models.CharField(_('incident type'), max_length=50)
    description = models.TextField(_('description'))
    severity = models.CharField(_('severity'), max_length=20)
    
    # Resolution
    status = models.CharField(_('status'), max_length=20, default='reported')
    resolution = models.TextField(_('resolution'), blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='resolved_incidents'
    )
    resolved_at = models.DateTimeField(_('resolved at'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('event incident')
        verbose_name_plural = _('event incidents')
        ordering = ['-incident_time']


class EventScheduleChange(models.Model):
    """Track changes to event schedules."""
    
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='schedule_changes')
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    # Change details
    previous_start = models.DateTimeField(_('previous start time'))
    new_start = models.DateTimeField(_('new start time'))
    previous_end = models.DateTimeField(_('previous end time'))
    new_end = models.DateTimeField(_('new end time'))
    reason = models.TextField(_('reason for change'))
    
    # Metadata
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    notification_sent = models.BooleanField(_('notification sent'), default=False)
    
    class Meta:
        verbose_name = _('event schedule change')
        verbose_name_plural = _('event schedule changes')
        ordering = ['-created_at']
