from django.shortcuts import render
from users.decorators import role_required

# Create your views here.

@role_required(['league_manager', 'admin'])
def create_league(request):
    # Only league managers and admins can access this view
    pass

@role_required('official')
def score_competition(request):
    # Only officials can access this view
    pass
