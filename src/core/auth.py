from ninja import Router
from django.shortcuts import redirect
from django.conf import settings
from social_django.utils import load_strategy, load_backend
from social_core.backends.oauth import BaseOAuth2
from social_core.exceptions import MissingBackend

router = Router()

@router.get("/auth/google")
def auth_url(request):
    """Return Google OAuth URL"""
    strategy = load_strategy(request)
    backend = load_backend(strategy=strategy, name='google-oauth2', redirect_uri=None)
    
    if isinstance(backend, BaseOAuth2):
        return {"url": backend.auth_url()}
    return {"error": "Invalid backend"}, 400

@router.get("/complete/google")
def complete_google_auth(request):
    """Complete Google OAuth process"""
    try:
        strategy = load_strategy(request)
        backend = load_backend(strategy=strategy, name='google-oauth2', redirect_uri=None)
        
        # Complete authentication process
        user = backend.complete(request)
        
        # Redirect to frontend with token
        redirect_url = f"{settings.FRONTEND_URL}/auth/callback?token={user.auth_token}"
        return redirect(redirect_url)
        
    except MissingBackend:
        return {"error": "Authentication failed"}, 400 