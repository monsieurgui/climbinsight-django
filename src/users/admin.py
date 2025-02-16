from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, Role

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)
    filter_horizontal = ('permissions',)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'username', 'first_name', 'last_name', 'is_active', 'email_verified', 'role')
    list_filter = ('is_active', 'email_verified', 'role', 'primary_login_method')
    search_fields = ('email', 'username', 'first_name', 'last_name')
    ordering = ('email',)
    
    fieldsets = (
        (None, {'fields': ('email', 'email_verified', 'password')}),
        (_('Personal info'), {'fields': (
            'username', 'first_name', 'last_name', 'date_of_birth', 
            'phone', 'avatar', 'climbing_level', 'bio', 'profile_picture'
        )}),
        (_('Additional info'), {'fields': (
            'emergency_contact', 'medical_info', 'certifications'
        )}),
        (_('Social accounts'), {'fields': (
            'google_id', 'facebook_id', 'primary_login_method'
        )}),
        (_('Roles and Permissions'), {'fields': (
            'is_active', 'is_staff', 'is_superuser', 'role', 'roles',
            'groups', 'user_permissions'
        )}),
        (_('Preferences'), {'fields': (
            'preferences', 'notification_settings'
        )}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )
