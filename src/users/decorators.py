from functools import wraps
from ninja.errors import HttpError

def role_required(roles):
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            if not request.auth or not request.auth.role:
                raise HttpError(401, "Authentication required")
            if request.auth.role.name not in roles:
                raise HttpError(403, "Insufficient permissions")
            return func(request, *args, **kwargs)
        return wrapper
    return decorator 