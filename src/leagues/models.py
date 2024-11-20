from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from users.models import Role  # Import Role model

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
    
    athletes = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='participating_leagues',
        blank=True,
        verbose_name=_('Athletes')
    )
    
    officials = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='officiating_leagues',
        blank=True,
        verbose_name=_('Officials')
    )
    
    technical_delegates = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='technical_delegate_leagues',
        blank=True,
        verbose_name=_('Technical Delegates')
    )
    
    governing_body = models.CharField(_('Governing Body'), max_length=255, blank=True, null=True)
    sanctioning_body = models.CharField(_('Sanctioning Body'), max_length=255, blank=True, null=True)
    
    seasonal_statistics = models.JSONField(_('Seasonal Statistics'), default=dict)
    historical_records = models.JSONField(_('Historical Records'), default=dict)
    
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('active', _('Active')),
        ('completed', _('Completed')),
        ('archived', _('Archived')),
    ]
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    
    # Timestamps and metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    # Add administrators field
    administrators = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='administered_leagues',
        blank=True,
        verbose_name=_('Administrators')
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_leagues',
        verbose_name=_('Created By')
    )

    class Meta:
        verbose_name = _('League')
        verbose_name_plural = _('Leagues')
        ordering = ['-start_date']

    def __str__(self):
        return self.name
        
    def get_current_rankings(self, category=None):
        """Get current rankings, optionally filtered by category"""
        rankings = self.ranking_system.get('current_rankings', {})
        if category:
            return rankings.get(category, [])
        return rankings
        
    def update_rankings(self, new_rankings, category=None):
        """Update rankings for the entire league or specific category"""
        current_rankings = self.ranking_system.get('current_rankings', {})
        if category:
            current_rankings[category] = new_rankings
        else:
            current_rankings = new_rankings
        self.ranking_system['current_rankings'] = current_rankings
        self.save()
    
    def user_has_access(self, user):
        """Check if user has access to view this league"""
        return (
            user.is_superuser or 
            user == self.created_by or
            user in self.administrators.all() or
            user in self.athletes.all() or
            user in self.officials.all() or
            user in self.technical_delegates.all()
        )

    def can_user_edit(self, user):
        """Check if user has edit permissions"""
        return (
            user.is_superuser or 
            user == self.created_by or 
            user in self.administrators.all() or
            user in self.technical_delegates.all()
        )

    def can_user_delete(self, user):
        """Check if user has delete permissions"""
        # Always allow creator and superuser to delete
        if user.is_superuser or user == self.created_by:
            return True
        
        # Check for admin role if user is an administrator
        if user in self.administrators.all():
            try:
                admin_role = Role.objects.get(name='admin')
                return user.roles.filter(id=admin_role.id).exists()
            except (Role.DoesNotExist, AttributeError):
                return False
                
        return False
