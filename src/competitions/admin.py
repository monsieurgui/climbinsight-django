from django.contrib import admin
from .models import Competition

@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'league', 'start_date', 'end_date', 'status')
    list_filter = ('status', 'league', 'ruleset')
    search_fields = ('name', 'league__name')
