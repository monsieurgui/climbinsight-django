from ninja import Router, Schema, Field
from ninja.errors import HttpError
from typing import List, Optional
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from ninja_jwt.authentication import JWTAuth
from django.db.models import Q

from users.api import User, UserResponseSchema
from .models import League
from competitions.api import CompetitionOut
from datetime import date
from .schemas import LeagueOut, LeagueIn, BulkLeagueIds, LeagueUpdateSchema
from users.models import Role  # Import Role model

router = Router(auth=JWTAuth())

# Endpoints
@router.get("/", response=List[LeagueOut])
def list_leagues(
    request,
    search: Optional[str] = None,
    active_only: bool = False,
    category: Optional[str] = None
):
    """List leagues that the user has access to"""
    user = request.auth
    if not user:
        raise HttpError(401, "Authentication required")

    if user.is_superuser:
        queryset = League.objects.all()
    else:
        queryset = League.objects.filter(
            Q(administrators=user) |
            Q(athletes=user) |
            Q(officials=user) |
            Q(technical_delegates=user) |
            Q(created_by=user)
        ).distinct()

    if search:
        queryset = queryset.filter(name__icontains=search)
    if active_only:
        queryset = queryset.filter(is_active=True)
    if category:
        queryset = queryset.filter(categories__contains=[category])
    
    return queryset

@router.get("/{league_id}", response=LeagueOut)
def get_league(request, league_id: int):
    """Get a specific league if user has access to it"""
    user = request.auth
    if not user:
        raise HttpError(401, "Authentication required")

    league = get_object_or_404(League, id=league_id)
    if not league.user_has_access(user):
        raise HttpError(403, "You don't have permission to view this league")
    
    return league

@router.post("/", response=LeagueOut)
def create_league(request, payload: LeagueIn):
    """Create a new league"""
    user = request.auth
    if not user:
        raise HttpError(401, "Authentication required")

    try:
        # Create league with required fields
        league_data = {
            'name': payload.name,
            'start_date': payload.start_date,
            'end_date': payload.end_date,
            'description': payload.description,
            'categories': payload.categories,
            'status': payload.status,
            'is_active': payload.is_active,
            'created_by': user
        }
        
        # Add optional fields if provided
        if payload.governing_body:
            league_data['governing_body'] = payload.governing_body
        if payload.sanctioning_body:
            league_data['sanctioning_body'] = payload.sanctioning_body
        
        league = League.objects.create(**league_data)
        
        # Add creator as administrator
        league.administrators.add(user)
        
        return league
        
    except ValueError as e:
        raise HttpError(400, str(e))
    except Exception as e:
        raise HttpError(500, f"Internal server error: {str(e)}")

@router.put("/{league_id}", response=LeagueOut)
def update_league(request, league_id: int, payload: LeagueUpdateSchema):
    """Update a league if user has edit permissions"""
    user = request.auth
    if not user:
        raise HttpError(401, "Authentication required")

    try:
        league = get_object_or_404(League, id=league_id)
        
        if not league.can_user_edit(user):
            raise HttpError(403, "You don't have permission to edit this league")
        
        # Update only provided fields
        update_data = payload.dict(exclude_unset=True, exclude_none=True)
        
        # Validate dates if both are provided
        if 'start_date' in update_data and 'end_date' in update_data:
            if update_data['end_date'] < update_data['start_date']:
                raise ValueError("End date must be after start date")
        
        # Update fields
        for key, value in update_data.items():
            if hasattr(league, key):
                setattr(league, key, value)
        
        league.save()
        return league
        
    except ValueError as e:
        raise HttpError(400, str(e))
    except Exception as e:
        raise HttpError(500, f"Internal server error: {str(e)}")

@router.delete("/{league_id}")
def delete_league(request, league_id: int):
    """Delete a league if user has delete permissions"""
    user = request.auth
    if not user:
        raise HttpError(401, "Authentication required")

    try:
        league = get_object_or_404(League, id=league_id)
        
        # Allow deletion if user is either:
        # 1. The creator of the league
        # 2. A superuser
        # 3. An administrator with admin role (if role exists)
        if user.is_superuser or user == league.created_by:
            league.delete()
            return {"success": True, "message": "League successfully deleted"}
            
        # Additional check for admin role if user is an administrator
        if user in league.administrators.all():
            try:
                admin_role = Role.objects.get(name='admin')
                if user.roles.filter(id=admin_role.id).exists():
                    league.delete()
                    return {"success": True, "message": "League successfully deleted"}
            except (Role.DoesNotExist, AttributeError):
                pass
        
        raise HttpError(403, "You don't have permission to delete this league")
        
    except Exception as e:
        if isinstance(e, HttpError):
            raise e
        raise HttpError(500, "Internal server error while trying to delete league")

@router.get("/{league_id}/competitions", response=List[CompetitionOut])
def get_league_competitions(request, league_id: int):
    league = get_object_or_404(League, id=league_id)
    return league.competitions.all()  # This works because of the related_name in Competition model

@router.get("/{league_id}/summary", response=dict)
def get_league_summary(request, league_id: int):
    league = get_object_or_404(League, id=league_id)
    competitions = league.competitions.all()
    
    return {
        "total_competitions": competitions.count(),
        "active_competitions": competitions.filter(status='in_progress').count(),
        "total_participants": competitions.filter(status__in=['in_progress', 'completed']).count(),
        "categories_distribution": {
            category: competitions.filter(category=category).count()
            for category in league.categories
        }
    }

@router.post("/bulk-activate", response=dict)
def bulk_activate_leagues(request, payload: BulkLeagueIds):
    updated = League.objects.filter(id__in=payload.ids).update(is_active=True)
    return {"updated": updated}

@router.post("/bulk-deactivate", response=dict)
def bulk_deactivate_leagues(request, payload: BulkLeagueIds):
    updated = League.objects.filter(id__in=payload.ids).update(is_active=False)
    return {"updated": updated}

@router.get("/{league_id}/athletes", response=List[UserResponseSchema])
def get_league_athletes(request, league_id: int):
    """Get all athletes registered in a league"""
    league = get_object_or_404(League, id=league_id)
    return league.athletes.all()

@router.post("/{league_id}/athletes/{user_id}")
def add_athlete_to_league(request, league_id: int, user_id: int):
    """Add an athlete to a league"""
    league = get_object_or_404(League, id=league_id)
    user = get_object_or_404(User, id=user_id)
    league.athletes.add(user)
    return {"success": True}

@router.delete("/{league_id}/athletes/{user_id}")
def remove_athlete_from_league(request, league_id: int, user_id: int):
    """Remove an athlete from a league"""
    league = get_object_or_404(League, id=league_id)
    user = get_object_or_404(User, id=user_id)
    league.athletes.remove(user)
    return {"success": True}

@router.get("/{league_id}/officials", response=List[UserResponseSchema])
def get_league_officials(request, league_id: int):
    """Get all officials assigned to a league"""
    league = get_object_or_404(League, id=league_id)
    return league.officials.all()

@router.post("/{league_id}/officials/{user_id}")
def add_official_to_league(request, league_id: int, user_id: int):
    """Add an official to a league"""
    league = get_object_or_404(League, id=league_id)
    user = get_object_or_404(User, id=user_id)
    if not user.has_role('official'):
        return {"error": "User is not an official"}, 400
    league.officials.add(user)
    return {"success": True}

@router.get("/{league_id}/rankings", response=dict)
def get_league_rankings(request, league_id: int, category: Optional[str] = None):
    """Get league rankings, optionally filtered by category"""
    league = get_object_or_404(League, id=league_id)
    return league.get_current_rankings(category)

@router.post("/{league_id}/rankings")
def update_league_rankings(request, league_id: int, rankings: dict, category: Optional[str] = None):
    """Update league rankings"""
    league = get_object_or_404(League, id=league_id)
    league.update_rankings(rankings, category)
    return {"success": True}

@router.get("/ping")
def ping(request):
    """Test endpoint to verify router is mounted"""
    return {"message": "leagues router is responding"}

@router.post("/ping")
def ping_post(request):
    """Test endpoint to verify POST methods"""
    return {"message": "POST to leagues router is working"}

@router.post("/{league_id}/administrators/{user_id}")
def add_administrator(request, league_id: int, user_id: int):
    league = get_object_or_404(League, id=league_id)
    
    if not league.can_user_edit(request.auth):
        raise HttpError(403, "You don't have permission to modify administrators")
    
    User = get_user_model()
    new_admin = get_object_or_404(User, id=user_id)
    league.administrators.add(new_admin)
    return {"success": True}