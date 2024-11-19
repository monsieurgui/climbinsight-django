from django.db import models
from django.utils.translation import gettext_lazy as _
from leagues.models import League
from django.conf import settings

# Create your models here.

class Competition(models.Model):
    league = models.ForeignKey(League, on_delete=models.CASCADE, related_name='competitions')
    name = models.CharField(_('Name'), max_length=255)
    description = models.TextField(_('Description'), blank=True)
    location = models.CharField(_('Location'), max_length=255)
    start_datetime = models.DateTimeField(_('Start Date and Time'))
    end_datetime = models.DateTimeField(_('End Date and Time'))
    
    RULESET_CHOICES = [
        ('standard', _('Standard')),
        ('modified', _('Modified')),
        ('youth', _('Youth')),
        # Add other rulesets
    ]
    ruleset = models.CharField(_('Ruleset'), max_length=50, choices=RULESET_CHOICES)
    
    # Technical details
    technical_delegate = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # Changed from 'auth.User' to settings.AUTH_USER_MODEL
        on_delete=models.SET_NULL,
        null=True,
        related_name='competitions_as_delegate'
    )
    
    # Status tracking
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('published', _('Published')),
        ('in_progress', _('In Progress')),
        ('completed', _('Completed')),
        ('cancelled', _('Cancelled')),
    ]
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='draft')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Competition')
        verbose_name_plural = _('Competitions')
        ordering = ['start_datetime']

    def __str__(self):
        return f"{self.name} ({self.league.name})"
