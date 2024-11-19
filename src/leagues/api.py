from ninja import Router, Schema, Field
from ninja.security import HttpBearer
from ninja.errors import HttpError
from typing import List, Optional
from django.shortcuts import get_object_or_404
from .models import League
from competitions.api import CompetitionOut  # Import the competition schema
from datetime import date

class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        # Implement your token authentication logic here
        return token

router = Router(auth=AuthBearer())

# Schemas
class LeagueOut(Schema):
    id: int
    name: str
    start_date: str
    end_date: str
    description: str
    categories: list
    ranking_system: dict
    qualification_criteria: dict
    is_active: bool

class LeagueIn(Schema):
    name: str = Field(..., min_length=3, max_length=255)
    start_date: date
    end_date: date
    description: str = Field(default="")
    categories: list = Field(default_factory=list)
    ranking_system: dict = Field(default_factory=dict)
    qualification_criteria: dict = Field(default_factory=dict)
    is_active: bool = True

    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("End date must be after start date")

class LeagueSummary(Schema):
    total_competitions: int
    active_competitions: int
    total_participants: int
    categories_distribution: dict

class BulkLeagueIds(Schema):
    ids: List[int]

# Endpoints
@router.get("/", response=List[LeagueOut])
def list_leagues(
    request,
    search: Optional[str] = None,
    active_only: bool = False,
    category: Optional[str] = None
):
    queryset = League.objects.all()
    
    if search:
        queryset = queryset.filter(name__icontains=search)
    
    if active_only:
        queryset = queryset.filter(is_active=True)
    
    if category:
        queryset = queryset.filter(categories__contains=[category])
    
    return queryset

@router.get("/{league_id}", response=LeagueOut)
def get_league(request, league_id: int):
    return get_object_or_404(League, id=league_id)

@router.post("/", response=LeagueOut)
def create_league(request, payload: LeagueIn):
    try:
        payload.validate_dates()
        league = League.objects.create(**payload.dict())
        return league
    except ValueError as e:
        raise HttpError(400, str(e))
    except Exception as e:
        raise HttpError(500, "Internal server error")

@router.put("/{league_id}", response=LeagueOut)
def update_league(request, league_id: int, payload: LeagueIn):
    league = get_object_or_404(League, id=league_id)
    for attr, value in payload.dict().items():
        setattr(league, attr, value)
    league.save()
    return league

@router.delete("/{league_id}")
def delete_league(request, league_id: int):
    league = get_object_or_404(League, id=league_id)
    league.delete()
    return {"success": True}

@router.get("/{league_id}/competitions", response=List[CompetitionOut])
def get_league_competitions(request, league_id: int):
    league = get_object_or_404(League, id=league_id)
    return league.competitions.all()  # This works because of the related_name in Competition model

@router.get("/{league_id}/summary", response=LeagueSummary)
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