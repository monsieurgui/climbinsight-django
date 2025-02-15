from functools import wraps
from ninja.errors import HttpError

def role_required(roles):
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            if not request.auth or not request.auth.roles:
                raise HttpError(401, "Authentication required")
            user_roles = request.auth.roles
            if not any(role in user_roles for role in roles):
                raise HttpError(403, "Insufficient permissions")
            return func(request, *args, **kwargs)
        return wrapper
    return decorator 