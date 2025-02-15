from functools import wraps
from ninja.security import HttpBearer
from django.shortcuts import get_object_or_404
from .models import Competition, CompetitionStaff
from ninja_jwt.authentication import JWTAuth

class CompetitionRoleAuth(JWTAuth):
    def authenticate(self, request, competition_id=None, **kwargs):
        # First authenticate using JWT
        result = super().authenticate(request)
        if not result:
            return None
        
        user = result
        
        # If no competition_id is provided, just return the authenticated user
        if not competition_id:
            return user
            
        # Check if user has any role in the competition
        try:
            competition = Competition.objects.get(id=competition_id)
            staff = CompetitionStaff.objects.get(competition=competition, user=user)
            return user
        except (Competition.DoesNotExist, CompetitionStaff.DoesNotExist):
            return None

def require_competition_role(allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, competition_id, *args, **kwargs):
            # Get the competition
            competition = get_object_or_404(Competition, id=competition_id)
            
            # Get the user's role
            try:
                staff = CompetitionStaff.objects.get(
                    competition=competition,
                    user=request.auth
                )
                
                # Check if user's role is in allowed roles
                if staff.role in allowed_roles:
                    return view_func(request, competition_id, *args, **kwargs)
                    
            except CompetitionStaff.DoesNotExist:
                pass
                
            return {"error": "Insufficient permissions"}
            
        return wrapper
    return decorator 