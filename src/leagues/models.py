from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from users.models import Role  # Import Role model
from .ranking import RankingRule, FQMERules, IFSCRules
from typing import Dict

# Create your models here.

class Category(models.Model):
    """Competition categories (e.g., senior male, junior female, etc.)"""
    
    name = models.CharField(_('name'), max_length=100)
    description = models.TextField(_('description'), blank=True)
    age_range = models.JSONField(_('age range'), null=True, blank=True)
    gender = models.CharField(_('gender'), max_length=20, blank=True)
    skill_level = models.CharField(_('skill level'), max_length=50, blank=True)
    is_active = models.BooleanField(_('active'), default=True)
    
    class Meta:
        verbose_name = _('category')
        verbose_name_plural = _('categories')
        
    def __str__(self):
        return self.name


class League(models.Model):
    """Main league model."""
    
    name = models.CharField(_('name'), max_length=255)
    description = models.TextField(_('description'), blank=True)
    start_date = models.DateField(_('start date'), null=True)
    end_date = models.DateField(_('end date'), null=True)
    
    # Relationships
    categories = models.ManyToManyField(Category, related_name='leagues')
    athletes = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='athlete_leagues',
        limit_choices_to={'roles__contains': ['ATHLETE']}
    )
    officials = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='official_leagues',
        limit_choices_to={'roles__contains': ['OFFICIAL']}
    )
    technical_delegates = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='delegate_leagues',
        limit_choices_to={'roles__contains': ['TECH_DELEGATE']}
    )
    administrators = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='administered_leagues',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_leagues'
    )
    
    # League settings
    ranking_system = models.JSONField(_('ranking system configuration'), default=dict)
    qualification_criteria = models.JSONField(_('qualification criteria'), default=dict)
    rules_and_regulations = models.JSONField(_('rules and regulations'), default=dict)
    ruleset_type = models.CharField(_('ruleset type'), max_length=50, default='IFSC',
                                  choices=[('IFSC', 'IFSC Rules'), ('FQME', 'FQME Rules')])
    ruleset_config = models.JSONField(_('ruleset configuration'), default=dict,
                                    help_text=_('Custom configuration for the ruleset'))
    derogation_athletes = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='derogation_leagues',
        blank=True,
        help_text=_('Athletes participating under derogation')
    )
    
    # Governance
    governing_body = models.CharField(_('governing body'), max_length=255, null=True, blank=True)
    sanctioning_body = models.CharField(_('sanctioning body'), max_length=255, null=True, blank=True)
    
    # Status and metadata
    status = models.CharField(_('status'), max_length=20, default='draft')
    is_active = models.BooleanField(_('active'), default=True)
    registration_open = models.BooleanField(_('registration open'), default=False)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('league')
        verbose_name_plural = _('leagues')
        ordering = ['-start_date']
        
    def __str__(self):
        return self.name

    def get_ruleset(self) -> RankingRule:
        """Get the ruleset instance for this league."""
        if self.ruleset_type == 'FQME':
            return FQMERules(**self.ruleset_config)
        return IFSCRules(**self.ruleset_config)
    
    def get_current_rankings(self, category=None):
        """Get current rankings, optionally filtered by category."""
        rankings = self.ranking_system.get('current_rankings', {})
        if category:
            return rankings.get(str(category) if isinstance(category, (int, str)) else category.name, [])
        return rankings
    
    def update_rankings(self, new_rankings, category=None):
        """Update rankings for the entire league or specific category."""
        current_rankings = self.ranking_system.get('current_rankings', {})
        if category:
            category_key = str(category) if isinstance(category, (int, str)) else category.name
            current_rankings[category_key] = new_rankings
        else:
            current_rankings = new_rankings
        self.ranking_system['current_rankings'] = current_rankings
        self.save()
    
    def get_scoring_config(self, discipline: str) -> dict:
        """Get scoring configuration for a specific discipline."""
        ruleset = self.get_ruleset()
        return {
            'type': self.ruleset_type,
            'points_table': ruleset.get_points_table().get(discipline, {}),
            'qualification_criteria': ruleset.get_qualification_criteria(),
            'features': ruleset.get_rule_info()['features']
        }

    def has_derogation(self, athlete_id: int) -> bool:
        """Check if an athlete has derogation status."""
        return self.derogation_athletes.filter(id=athlete_id).exists()

    def add_derogation(self, athlete_id: int) -> None:
        """Add derogation status to an athlete."""
        self.derogation_athletes.add(athlete_id)

    def remove_derogation(self, athlete_id: int) -> None:
        """Remove derogation status from an athlete."""
        self.derogation_athletes.remove(athlete_id)

    def get_derogation_config(self) -> Dict:
        """Get derogation configuration from ruleset."""
        ruleset = self.get_ruleset()
        return ruleset.config.get('derogation', {
            'enabled': False,
            'rules': {
                'allow_participation': True,
                'points_handling': 'no_points',
                'ranking_display': 'with_original_rank'
            }
        })


class LeagueRanking(models.Model):
    """Rankings for athletes within a league."""
    
    league = models.ForeignKey(League, on_delete=models.CASCADE, related_name='rankings')
    athlete = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    
    points = models.IntegerField(_('points'), default=0)
    ranking = models.IntegerField(_('ranking'))
    competitions_attended = models.IntegerField(_('competitions attended'), default=0)
    best_results = models.JSONField(_('best results'), default=list)
    statistics = models.JSONField(_('statistics'), default=dict)
    original_points = models.IntegerField(_('original points before derogation'), null=True, blank=True)
    original_ranking = models.IntegerField(_('original ranking before derogation'), null=True, blank=True)
    points_source = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='points_beneficiary',
        help_text=_('Athlete whose points were redistributed to this athlete')
    )
    
    class Meta:
        verbose_name = _('league ranking')
        verbose_name_plural = _('league rankings')
        unique_together = ['league', 'athlete', 'category']
        ordering = ['category', 'ranking']

    def is_under_derogation(self) -> bool:
        """Check if this ranking is for an athlete under derogation."""
        return self.league.has_derogation(self.athlete_id)

    def get_display_data(self) -> Dict:
        """Get ranking data formatted according to derogation rules."""
        derogation_config = self.league.get_derogation_config()
        
        if not self.is_under_derogation():
            return {
                'ranking': self.ranking,
                'points': self.points,
                'competitions_attended': self.competitions_attended,
                'best_results': self.best_results,
                'statistics': self.statistics
            }
        
        # Athlete is under derogation
        display_data = {
            'ranking': self.original_ranking if derogation_config['rules']['ranking_display'] == 'with_original_rank' else None,
            'points': 0,  # No points for derogation athletes
            'competitions_attended': self.competitions_attended,
            'best_results': self.best_results,
            'statistics': self.statistics,
            'derogation': True,
            'derogation_note': derogation_config['rules']['display_note']
        }
        
        return display_data


class LeagueSponsor(models.Model):
    """Sponsors associated with a league."""
    
    league = models.ForeignKey(League, on_delete=models.CASCADE, related_name='sponsors')
    name = models.CharField(_('name'), max_length=255)
    logo = models.URLField(_('logo URL'))
    website = models.URLField(_('website'), blank=True)
    sponsorship_level = models.CharField(_('sponsorship level'), max_length=50)
    sponsorship_details = models.JSONField(_('sponsorship details'))
    is_active = models.BooleanField(_('active'), default=True)
    
    class Meta:
        verbose_name = _('league sponsor')
        verbose_name_plural = _('league sponsors')


class LeagueDocument(models.Model):
    """Documents associated with a league."""
    
    league = models.ForeignKey(League, on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(_('title'), max_length=255)
    document_type = models.CharField(_('document type'), max_length=50)
    file_url = models.URLField(_('file URL'))
    version = models.CharField(_('version'), max_length=20)
    uploaded_at = models.DateTimeField(_('uploaded at'), auto_now_add=True)
    is_public = models.BooleanField(_('public'), default=False)
    
    class Meta:
        verbose_name = _('league document')
        verbose_name_plural = _('league documents')
        ordering = ['-uploaded_at']

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
