# src/core/permissions.py
from ninja.security import HttpBearer
from ninja_jwt.authentication import JWTAuth

class HasLeaguePermission(JWTAuth):
    def authenticate(self, request, league_id):
        result = super().authenticate(request)
        if not result:
            return None
        user = result
        # Add permission logic
        return user