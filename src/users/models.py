from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

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
