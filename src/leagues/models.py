from django.db import models
from django.utils.translation import gettext_lazy as _

# Create your models here.

class League(models.Model):
    name = models.CharField(_('Name'), max_length=255)
    start_date = models.DateField(_('Start Date'))
    end_date = models.DateField(_('End Date'))
    description = models.TextField(_('Description'), blank=True)
    
    # Categories as choices
    CATEGORY_CHOICES = [
        ('senior_male', _('Senior Male')),
        ('senior_female', _('Senior Female')),
        ('junior_male', _('Junior Male')),
        ('junior_female', _('Junior Female')),
        ('recreational', _('Recreational')),
    ]
    
    categories = models.JSONField(_('Categories'), default=list)
    ranking_system = models.JSONField(_('Ranking System'), default=dict)
    qualification_criteria = models.JSONField(_('Qualification Criteria'), default=dict)
    
    # Timestamps and metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _('League')
        verbose_name_plural = _('Leagues')
        ordering = ['-start_date']

    def __str__(self):
        return self.name
