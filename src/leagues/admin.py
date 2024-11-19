from django.contrib import admin
from .models import League

@admin.register(League)
class LeagueAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active', 'start_date')
    search_fields = ('name',)
