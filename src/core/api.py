from ninja import NinjaAPI
from ninja_extra import NinjaExtraAPI, ControllerBase
from ninja_jwt.controller import NinjaJWTDefaultController
from django.conf import settings

# Create API instance with Swagger documentation
api = NinjaExtraAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description=settings.API_DESCRIPTION,
    openapi_url="/openapi.json",  # URL for OpenAPI schema
    docs_url="/docs",  # Swagger UI will be served at /api/docs
    csrf=False,  # Disable CSRF for API endpoints
)

# Register JWT controller first
api.register_controllers(NinjaJWTDefaultController)

# Tags for API organization
class Tags:
    auth = "Authentication"
    users = "Users"
    leagues = "Leagues"
    competitions = "Competitions"
    events = "Events"
    gyms = "Gyms"

# Dictionary to track registered routers
registered_routers = {}

def register_router(path: str, router, tag: str):
    """Helper function to safely register routers"""
    if path not in registered_routers:
        try:
            api.add_router(path, router, tags=[tag])
            registered_routers[path] = router
        except Exception as e:
            print(f"Failed to register router at {path}: {str(e)}")

# Include routers from each app
try:
    from leagues.api import router as leagues_router
    register_router("/leagues/", leagues_router, Tags.leagues)
except ImportError:
    pass

try:
    from competitions.api import router as competitions_router
    register_router("/competitions/", competitions_router, Tags.competitions)
except ImportError:
    pass

try:
    from events.api import router as events_router
    register_router("/events/", events_router, Tags.events)
except ImportError:
    pass

try:
    from gyms.api import router as gyms_router
    register_router("/gyms/", gyms_router, Tags.gyms)
except ImportError:
    pass

# Register users router last since it contains the JWT controller
try:
    from users.api import router as users_router
    register_router("/users/", users_router, Tags.users)
except ImportError:
    pass 