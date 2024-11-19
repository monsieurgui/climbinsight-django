from ninja import Router, Schema
from ninja.security import HttpBearer
from typing import List
from django.shortcuts import get_object_or_404
from .models import Competition
from django.contrib.auth import get_user_model
from users.decorators import role_required

class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        # Implement your token authentication logic here
        # This is just a placeholder
        return token

router = Router(auth=AuthBearer())

# Schemas
class CompetitionOut(Schema):
    id: int
    name: str
    league_id: int
    start_datetime: str
    end_datetime: str
    status: str
    location: str
    ruleset: str

class CompetitionIn(Schema):
    name: str
    league_id: int
    start_datetime: str
    end_datetime: str
    location: str
    ruleset: str

# Endpoints
@router.get("/", response=List[CompetitionOut])
def list_competitions(request):
    return Competition.objects.all()

@router.get("/{competition_id}", response=CompetitionOut)
def get_competition(request, competition_id: int):
    return get_object_or_404(Competition, id=competition_id)

@router.post("/", response=CompetitionOut)
@role_required(['Admin', 'Technical Delegate'])
def create_competition(request, payload: CompetitionIn):
    competition = Competition.objects.create(**payload.dict())
    return competition

@router.put("/{competition_id}", response=CompetitionOut)
def update_competition(request, competition_id: int, payload: CompetitionIn):
    competition = get_object_or_404(Competition, id=competition_id)
    for attr, value in payload.dict().items():
        setattr(competition, attr, value)
    competition.save()
    return competition

@router.delete("/{competition_id}")
def delete_competition(request, competition_id: int):
    competition = get_object_or_404(Competition, id=competition_id)
    competition.delete()
    return {"success": True} 