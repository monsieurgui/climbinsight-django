from ninja import Router, Schema, Field
from ninja.security import HttpBearer
from typing import List, Optional, Dict
from django.shortcuts import get_object_or_404
from .models import Competition, CompetitionRegistration, CompetitionResult, Appeal
from django.contrib.auth import get_user_model
from users.decorators import role_required
from datetime import datetime
from django.db.models import Q
from django.core.cache import cache

class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        # Implement your token authentication logic here
        # This is just a placeholder
        return token

router = Router(auth=AuthBearer())

# Schemas
class LocationSchema(Schema):
    venue: str
    address: str
    city: str
    country: str
    coordinates: Optional[Dict[str, float]] = None
    venue_details: Optional[dict] = None

class SafetyProtocolSchema(Schema):
    general_guidelines: dict
    emergency_contacts: List[dict]
    evacuation_plan: dict
    medical_procedures: dict
    covid_protocols: Optional[dict] = None

class CompetitionOut(Schema):
    id: int
    name: str
    description: str
    league_id: int
    start_date: datetime
    end_date: datetime
    location: LocationSchema
    status: str
    registration_deadline: Optional[datetime]
    categories: List[int]
    ruleset: dict
    safety_protocols: SafetyProtocolSchema
    is_active: bool

class CompetitionIn(Schema):
    name: str
    description: str
    league_id: int
    start_date: datetime
    end_date: datetime
    location: LocationSchema
    registration_deadline: Optional[datetime]
    categories: List[int]
    ruleset: dict
    safety_protocols: Optional[SafetyProtocolSchema] = None

class RegistrationSchema(Schema):
    athlete_id: int
    category_id: int
    waiver_signed: bool = False
    medical_clearance: bool = False
    requirements_met: dict = {}

class AppealSchema(Schema):
    athlete_id: int
    event_id: int
    reason: str
    evidence: Optional[dict] = None

class ResultSchema(Schema):
    athlete_id: int
    category_id: int
    ranking: int
    score: dict
    attempts: List[dict]
    disqualified: bool = False
    disqualification_reason: Optional[str] = None

# Endpoints
@router.get("/", response=List[CompetitionOut])
def list_competitions(request, league_id: Optional[int] = None, status: Optional[str] = None):
    """List all competitions with optional filtering."""
    competitions = Competition.objects.all()
    if league_id:
        competitions = competitions.filter(league_id=league_id)
    if status:
        competitions = competitions.filter(status=status)
    return competitions

@router.get("/{competition_id}", response=CompetitionOut)
def get_competition(request, competition_id: int):
    """Get detailed information about a specific competition."""
    return get_object_or_404(Competition, id=competition_id)

@router.post("/", response=CompetitionOut)
@role_required(['Admin', 'Technical Delegate'])
def create_competition(request, payload: CompetitionIn):
    """Create a new competition."""
    competition = Competition.objects.create(
        name=payload.name,
        description=payload.description,
        league_id=payload.league_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        location=payload.location.dict(),
        registration_deadline=payload.registration_deadline,
        ruleset=payload.ruleset,
        safety_protocols=payload.safety_protocols.dict() if payload.safety_protocols else {}
    )
    if payload.categories:
        competition.categories.set(payload.categories)
    return competition

@router.put("/{competition_id}", response=CompetitionOut)
@role_required(['Admin', 'Technical Delegate'])
def update_competition(request, competition_id: int, payload: CompetitionIn):
    """Update competition details."""
    competition = get_object_or_404(Competition, id=competition_id)
    for attr, value in payload.dict(exclude_unset=True).items():
        if attr == 'categories':
            competition.categories.set(value)
        else:
            setattr(competition, attr, value)
    competition.save()
    return competition

@router.delete("/{competition_id}")
@role_required(['Admin'])
def delete_competition(request, competition_id: int):
    """Delete a competition."""
    competition = get_object_or_404(Competition, id=competition_id)
    competition.delete()
    return {"success": True}

# Registration Management
@router.post("/{competition_id}/registrations", response=dict)
def register_athlete(request, competition_id: int, payload: RegistrationSchema):
    """Register an athlete for a competition."""
    competition = get_object_or_404(Competition, id=competition_id)
    
    # Check registration deadline
    if competition.registration_deadline and datetime.now() > competition.registration_deadline:
        return {"error": "Registration deadline has passed"}, 400
    
    registration = CompetitionRegistration.objects.create(
        competition=competition,
        athlete_id=payload.athlete_id,
        category_id=payload.category_id,
        waiver_signed=payload.waiver_signed,
        medical_clearance=payload.medical_clearance,
        requirements_met=payload.requirements_met
    )
    return {"success": True, "registration_id": registration.id}

@router.get("/{competition_id}/registrations", response=List[dict])
def list_registrations(request, competition_id: int, category_id: Optional[int] = None):
    """List all registrations for a competition."""
    registrations = CompetitionRegistration.objects.filter(competition_id=competition_id)
    if category_id:
        registrations = registrations.filter(category_id=category_id)
    return registrations

# Results Management
@router.post("/{competition_id}/results", response=dict)
@role_required(['Admin', 'Official'])
def submit_result(request, competition_id: int, payload: ResultSchema):
    """Submit a result for an athlete."""
    result = CompetitionResult.objects.create(
        competition_id=competition_id,
        athlete_id=payload.athlete_id,
        category_id=payload.category_id,
        ranking=payload.ranking,
        score=payload.score,
        attempts=payload.attempts,
        disqualified=payload.disqualified,
        disqualification_reason=payload.disqualification_reason
    )
    return {"success": True, "result_id": result.id}

@router.get("/{competition_id}/results", response=List[dict])
def get_results(request, competition_id: int, category_id: Optional[int] = None):
    """Get results for a competition."""
    results = CompetitionResult.objects.filter(competition_id=competition_id)
    if category_id:
        results = results.filter(category_id=category_id)
    return results.order_by('category', 'ranking')

# Appeals Management
@router.post("/{competition_id}/appeals", response=dict)
def submit_appeal(request, competition_id: int, payload: AppealSchema):
    """Submit an appeal for a competition event."""
    appeal = Appeal.objects.create(
        competition_id=competition_id,
        athlete_id=payload.athlete_id,
        event_id=payload.event_id,
        reason=payload.reason,
        evidence=payload.evidence
    )
    return {"success": True, "appeal_id": appeal.id}

@router.get("/{competition_id}/appeals", response=List[dict])
@role_required(['Admin', 'Technical Delegate', 'Official'])
def list_appeals(request, competition_id: int, status: Optional[str] = None):
    """List all appeals for a competition."""
    appeals = Appeal.objects.filter(competition_id=competition_id)
    if status:
        appeals = appeals.filter(status=status)
    return appeals.order_by('-submitted_at')

@router.put("/{competition_id}/appeals/{appeal_id}", response=dict)
@role_required(['Admin', 'Technical Delegate'])
def decide_appeal(request, competition_id: int, appeal_id: int, decision: str, details: str):
    """Make a decision on an appeal."""
    appeal = get_object_or_404(Appeal, id=appeal_id, competition_id=competition_id)
    appeal.status = 'accepted' if decision.lower() == 'accept' else 'rejected'
    appeal.decision = details
    appeal.decided_by = request.user
    appeal.decided_at = datetime.now()
    appeal.save()
    return {"success": True}

# Staff Management
@router.post("/{competition_id}/staff/officials", response=dict)
@role_required(['Admin', 'Technical Delegate'])
def assign_official(request, competition_id: int, user_id: int):
    """Assign an official to the competition."""
    competition = get_object_or_404(Competition, id=competition_id)
    competition.officials.add(user_id)
    return {"success": True}

@router.post("/{competition_id}/staff/medical", response=dict)
@role_required(['Admin', 'Technical Delegate'])
def assign_medical_staff(request, competition_id: int, user_id: int):
    """Assign medical staff to the competition."""
    competition = get_object_or_404(Competition, id=competition_id)
    competition.medical_staff.add(user_id)
    return {"success": True}

@router.post("/{competition_id}/staff/route-setters", response=dict)
@role_required(['Admin', 'Technical Delegate'])
def assign_route_setter(request, competition_id: int, user_id: int):
    """Assign a route setter to the competition."""
    competition = get_object_or_404(Competition, id=competition_id)
    competition.route_setters.add(user_id)
    return {"success": True} 