from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
import datetime

# Create your models here.
class Role(models.Model):
    """Custom roles for the application"""
    name = models.CharField(_('Name'), max_length=100, unique=True)
    description = models.TextField(_('Description'), blank=True)
    permissions = models.ManyToManyField(
        'auth.Permission',
        blank=True,
        related_name='custom_roles'
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('Role')
        verbose_name_plural = _('Roles')

class User(AbstractUser):
    """Custom user model for the application."""
    
    # Auth fields are inherited from AbstractUser:
    # - username
    # - password
    # - email
    # - first_name
    # - last_name
    # - is_active
    # - is_staff
    # - is_superuser
    # - date_joined
    
    # Additional fields
    date_of_birth = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    avatar = models.URLField(blank=True)
    
    # Social auth fields
    google_id = models.CharField(max_length=255, blank=True)
    facebook_id = models.CharField(max_length=255, blank=True)
    
    # Climbing-specific fields
    climbing_level = models.CharField(max_length=50, blank=True)
    
    # We'll add the gym relationship later when we create the Gym model
    # preferred_gym = models.ForeignKey('gyms.Gym', ...)
    
    # Add field to track primary login method
    primary_login_method = models.CharField(
        max_length=20,
        choices=[
            ('email', 'Email'),
            ('google', 'Google'),
            ('facebook', 'Facebook')
        ],
        default='email'
    )
    
    # Add field to track merged accounts
    merged_accounts = models.ManyToManyField(
        'self',
        symmetrical=False,
        related_name='merged_into',
        blank=True
    )
    
    # Add custom role
    role = models.ForeignKey(
        Role,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='users'
    )
    
    class Meta:
        db_table = 'users'
        
    def __str__(self):
        return self.email

    def merge_account(self, other_user):
        """Merge another user account into this one."""
        if other_user == self:
            return False
            
        # Transfer social auth connections
        for social in other_user.social_auth.all():
            social.user = self
            social.save()
            
        # Update any important user data if missing
        if not self.date_of_birth and other_user.date_of_birth:
            self.date_of_birth = other_user.date_of_birth
        if not self.phone_number and other_user.phone_number:
            self.phone_number = other_user.phone_number
        if not self.avatar and other_user.avatar:
            self.avatar = other_user.avatar
        if not self.climbing_level and other_user.climbing_level:
            self.climbing_level = other_user.climbing_level
            
        # Deactivate the other account
        other_user.is_active = False
        other_user.save()
        
        self.save()
        return True

    def has_role_permission(self, permission):
        """Check if user has permission through their role"""
        if not self.role:
            return False
        return permission in self.role.all_permissions

    def has_role(self, role_name):
        """Check if user has specific role"""
        return self.role and self.role.name == role_name

class Profile(models.Model):
    # ... existing profile fields ...

    # League-related fields
    OFFICIAL_ROLES = [
        ('judge', _('Judge')),
        ('technical', _('Technical Delegate')),
        ('chief', _('Chief Judge')),
        ('route_setter', _('Route Setter')),
    ]
    
    official_roles = models.JSONField(
        _('Official Roles'),
        default=list,
        help_text=_('List of official roles this user can perform')
    )
    
    official_certifications = models.JSONField(
        _('Official Certifications'),
        default=list,
        help_text=_('List of certifications held by the official')
    )
    
    athlete_categories = models.JSONField(
        _('Athlete Categories'),
        default=list,
        help_text=_('Categories in which this athlete competes')
    )
    
    # Optional: Competition history
    competition_history = models.JSONField(
        _('Competition History'),
        default=dict,
        blank=True,
        help_text=_('Historical record of competition participation and results')
    )

    # ... rest of the model ...

    def add_official_role(self, role):
        """Add an official role if it's valid and not already present"""
        if role in dict(self.OFFICIAL_ROLES) and role not in self.official_roles:
            self.official_roles.append(role)
            self.save()
            return True
        return False

    def remove_official_role(self, role):
        """Remove an official role if present"""
        if role in self.official_roles:
            self.official_roles.remove(role)
            self.save()
            return True
        return False

    def add_certification(self, certification_data):
        """
        Add a certification with validation date and expiry
        certification_data should be a dict with:
        {
            'name': str,
            'issuer': str,
            'date_issued': str (YYYY-MM-DD),
            'expiry_date': str (YYYY-MM-DD),
            'certification_number': str
        }
        """
        if certification_data not in self.official_certifications:
            self.official_certifications.append(certification_data)
            self.save()
            return True
        return False

    def add_athlete_category(self, category):
        """Add an athlete category if not already present"""
        if category not in self.athlete_categories:
            self.athlete_categories.append(category)
            self.save()
            return True
        return False

    def record_competition_result(self, competition_data):
        """
        Record a competition result
        competition_data should be a dict with:
        {
            'competition_id': int,
            'date': str (YYYY-MM-DD),
            'category': str,
            'placement': int,
            'points': int,
            'notes': str
        }
        """
        competition_id = str(competition_data['competition_id'])
        if competition_id not in self.competition_history:
            self.competition_history[competition_id] = competition_data
            self.save()
            return True
        return False

    def get_active_certifications(self):
        """Return list of non-expired certifications"""
        today = datetime.date.today()
        return [
            cert for cert in self.official_certifications
            if datetime.datetime.strptime(cert['expiry_date'], '%Y-%m-%d').date() > today
        ]

    def can_officiate_role(self, role):
        """Check if user can perform a specific official role"""
        return role in self.official_roles

    def get_competition_history_by_year(self, year):
        """Get competition history filtered by year"""
        return {
            comp_id: data
            for comp_id, data in self.competition_history.items()
            if data['date'].startswith(str(year))
        }

    class Meta:
        verbose_name = _('Profile')
        verbose_name_plural = _('Profiles')

    def __str__(self):
        return f"Profile for {self.user.email}"
