from ninja import NinjaAPI
from users.api import router as users_router
from competitions.api import router as competitions_router
from leagues.api import router as leagues_router

api = NinjaAPI()
api.add_router("/users/", users_router)
api.add_router("/competitions/", competitions_router)
api.add_router("/leagues/", leagues_router) 