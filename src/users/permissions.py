from ninja.security import HttpBearer
from ninja_jwt.authentication import JWTAuth
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

class HasRolePermission(JWTAuth):
    def __init__(self, required_roles):
        self.required_roles = required_roles if isinstance(required_roles, (list, tuple)) else [required_roles]
        super().__init__()

    def authenticate(self, request):
        result = super().authenticate(request)
        if not result:
            return None
        
        user = result
        if any(user.has_role(role) for role in self.required_roles):
            return user
        return None

def create_custom_permission(codename, name, content_type=None):
    """Helper function to create custom permissions"""
    if content_type is None:
        content_type = ContentType.objects.get_for_model(Permission)
    
    return Permission.objects.get_or_create(
        codename=codename,
        name=name,
        content_type=content_type
    )[0]

# Define role-based permissions
ROLE_ADMIN = 'Admin'
ROLE_TECHNICAL_DELEGATE = 'Technical Delegate'
ROLE_JUDGE = 'Judge'
ROLE_ATHLETE = 'Athlete'

# Define permission codenames
PERMISSION_VIEW_COMPETITION = 'view_competition'
PERMISSION_MANAGE_COMPETITION = 'manage_competition'
PERMISSION_JUDGE_COMPETITION = 'judge_competition'
PERMISSION_PARTICIPATE_COMPETITION = 'participate_competition'

# Usage example:
# @router.get("/competitions", auth=HasRolePermission([ROLE_ADMIN, ROLE_TECHNICAL_DELEGATE])) 