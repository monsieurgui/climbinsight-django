from django.core.exceptions import PermissionDenied

class RoleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        if hasattr(view_func, 'role_required'):
            required_roles = view_func.role_required
            if not any(request.user.has_role(role) for role in required_roles):
                raise PermissionDenied
        return None 