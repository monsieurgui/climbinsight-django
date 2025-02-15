from ninja import Router, Schema, Field, Query
from ninja.security import HttpBearer
from typing import List, Optional, Dict
from django.shortcuts import get_object_or_404
from .models import Competition, CompetitionRegistration, CompetitionResult, Appeal, Round
from django.contrib.auth import get_user_model
from users.decorators import role_required
from datetime import datetime, date
from django.db.models import Q, Count, Avg, Max, Min, F
from django.core.cache import cache
from ninja_jwt.authentication import JWTAuth

router = Router(auth=JWTAuth())

# Base Schemas
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

# Overview Response Schemas
class CompetitionEventSchema(Schema):
    id: int
    name: str
    event_type: str
    start_time: datetime
    end_time: datetime
    status: str
    location: dict

class CompetitionRegistrationOverviewSchema(Schema):
    athlete_id: int
    athlete_first_name: str
    athlete_last_name: str
    category_name: str
    waiver_signed: bool
    medical_clearance: bool

class CompetitionResultOverviewSchema(Schema):
    athlete_id: int
    athlete_first_name: str
    athlete_last_name: str
    category_name: str
    ranking: int
    score: dict

class CompetitionLeagueSchema(Schema):
    id: int
    name: str

class CompetitionOverviewSchema(Schema):
    id: int
    name: str
    status: str
    start_date: datetime
    end_date: datetime
    location: dict
    league: CompetitionLeagueSchema
    events: Optional[List[CompetitionEventSchema]] = None
    registrations: Optional[List[CompetitionRegistrationOverviewSchema]] = None
    results: Optional[List[CompetitionResultOverviewSchema]] = None

# Search and Filter Schemas
class CompetitionSearchSchema(Schema):
    query: Optional[str] = None
    league_id: Optional[int] = None
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    location_city: Optional[str] = None
    category_id: Optional[int] = None
    has_available_registration: Optional[bool] = None

class BulkCompetitionScheduleUpdate(Schema):
    competition_ids: List[int]
    start_date: date
    end_date: date
    reason: str

class CompetitionAnalyticsSchema(Schema):
    total_registrations: int
    registrations_by_category: Dict[str, int]
    average_score_by_category: Dict[str, float]
    participation_trends: Dict[str, int]
    completion_rate: float
    appeal_statistics: Dict[str, int]
    safety_incidents: Dict[str, int]
    performance_distribution: Dict[str, Dict[str, float]]

# Competition Schemas
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

# Registration Schemas
class RegistrationIn(Schema):
    athlete_id: int
    category_id: int
    waiver_signed: bool = False
    medical_clearance: bool = False
    requirements_met: dict = {}

class RegistrationOut(Schema):
    id: int
    athlete_id: int
    category_id: int
    status: str
    registration_date: datetime
    check_in_time: Optional[datetime]
    bib_number: Optional[str]
    waiver_signed: bool
    medical_clearance: bool
    requirements_met: dict

# Round Schemas
class RoundIn(Schema):
    name: str
    order: int
    number_of_problems: int
    time_limit: int
    format: str
    rules: dict = {}

class RoundOut(Schema):
    id: int
    name: str
    order: int
    number_of_problems: int
    time_limit: int
    format: str
    rules: dict
    competition_id: int

# Result Schemas
class AttemptSchema(Schema):
    problem_number: int
    achieved_top: bool
    top_attempts: int
    achieved_zone: bool
    zone_attempts: int
    time_spent: str

class ResultIn(Schema):
    athlete_id: int
    category_id: int
    round_id: int
    ranking: int
    attempts: List[AttemptSchema]
    disqualified: bool = False
    disqualification_reason: Optional[str] = None

class ResultOut(Schema):
    id: int
    athlete_id: int
    category_id: int
    round_id: int
    ranking: int
    score: dict
    attempts: List[AttemptSchema]
    disqualified: bool
    disqualification_reason: Optional[str]
    formatted_score: dict

# Appeal Schemas
class AppealIn(Schema):
    athlete_id: int
    round_id: int
    problem_number: int
    reason: str
    evidence: Optional[dict] = None

class AppealOut(Schema):
    id: int
    athlete_id: int
    round_id: int
    problem_number: int
    reason: str
    evidence: Optional[dict]
    status: str
    submitted_at: datetime
    decision: Optional[str]
    decided_by_id: Optional[int]
    decided_at: Optional[datetime]

# Response Schemas
class SuccessResponse(Schema):
    success: bool
    message: Optional[str] = None

class ErrorResponse(Schema):
    success: bool = False
    error: str

class CompetitionOverviewOut(Schema):
    competition: CompetitionOut
    rounds: List[RoundOut]
    registrations_count: int
    results_by_category: Dict[str, List[ResultOut]]
    appeals_count: int
    status_summary: dict

# Endpoints with enhanced responses
@router.get("/", response={200: List[CompetitionOut], 404: ErrorResponse})
def list_competitions(
    request, 
    league_id: Optional[int] = None, 
    status: Optional[str] = None,
    category_id: Optional[int] = None
):
    """List all competitions with optional filtering."""
    competitions = Competition.objects.all()
    if league_id:
        competitions = competitions.filter(league_id=league_id)
    if status:
        competitions = competitions.filter(status=status)
    if category_id:
        competitions = competitions.filter(categories__id=category_id)
    return 200, competitions

@router.get("/{competition_id}", response={200: CompetitionOverviewOut, 404: ErrorResponse})
def get_competition(request, competition_id: int):
    """Get detailed information about a specific competition."""
    competition = get_object_or_404(Competition, id=competition_id)
    
    # Prepare overview response
    overview = {
        "competition": competition,
        "rounds": Round.objects.filter(competition=competition),
        "registrations_count": CompetitionRegistration.objects.filter(competition=competition).count(),
        "results_by_category": {},
        "appeals_count": Appeal.objects.filter(competition=competition).count(),
        "status_summary": {
            "registered": CompetitionRegistration.objects.filter(competition=competition).count(),
            "checked_in": CompetitionRegistration.objects.filter(competition=competition, check_in_time__isnull=False).count(),
            "completed": CompetitionResult.objects.filter(competition=competition).values('athlete').distinct().count()
        }
    }
    
    # Get results by category
    for category in competition.categories.all():
        overview["results_by_category"][category.name] = CompetitionResult.objects.filter(
            competition=competition,
            category=category
        ).order_by('round__order', 'ranking')
    
    return 200, overview

@router.post("/", response={201: CompetitionOut, 400: ErrorResponse})
@role_required(['Admin', 'Technical Delegate'])
def create_competition(request, payload: CompetitionIn):
    """Create a new competition."""
    try:
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
        return 201, competition
    except Exception as e:
        return 400, {"error": str(e)}

@router.put("/{competition_id}", response={200: CompetitionOut, 404: ErrorResponse, 400: ErrorResponse})
@role_required(['Admin', 'Technical Delegate'])
def update_competition(request, competition_id: int, payload: CompetitionIn):
    """Update competition details."""
    try:
        competition = get_object_or_404(Competition, id=competition_id)
        for attr, value in payload.dict(exclude_unset=True).items():
            if attr == 'categories':
                competition.categories.set(value)
            else:
                setattr(competition, attr, value)
        competition.save()
        return 200, competition
    except Exception as e:
        return 400, {"error": str(e)}

@router.delete("/{competition_id}", response={200: SuccessResponse, 404: ErrorResponse})
@role_required(['Admin'])
def delete_competition(request, competition_id: int):
    """Delete a competition."""
    competition = get_object_or_404(Competition, id=competition_id)
    competition.delete()
    return 200, {"success": True, "message": "Competition deleted successfully"}

# Registration Management
@router.post("/{competition_id}/registrations", response={201: RegistrationOut, 400: ErrorResponse})
def register_athlete(request, competition_id: int, payload: RegistrationIn):
    """Register an athlete for a competition."""
    try:
        competition = get_object_or_404(Competition, id=competition_id)
        
        # Check registration deadline
        if competition.registration_deadline and datetime.now() > competition.registration_deadline:
            return 400, {"error": "Registration deadline has passed"}
        
        registration = CompetitionRegistration.objects.create(
            competition=competition,
            athlete_id=payload.athlete_id,
            category_id=payload.category_id,
            waiver_signed=payload.waiver_signed,
            medical_clearance=payload.medical_clearance,
            requirements_met=payload.requirements_met
        )
        return 201, registration
    except Exception as e:
        return 400, {"error": str(e)}

@router.get("/{competition_id}/registrations", response={200: List[RegistrationOut], 404: ErrorResponse})
def list_registrations(request, competition_id: int, category_id: Optional[int] = None):
    """List all registrations for a competition."""
    registrations = CompetitionRegistration.objects.filter(competition_id=competition_id)
    if category_id:
        registrations = registrations.filter(category_id=category_id)
    return 200, registrations

# Results Management
@router.post("/{competition_id}/results", response={201: ResultOut, 400: ErrorResponse})
@role_required(['Admin', 'Official'])
def submit_result(request, competition_id: int, payload: ResultIn):
    """Submit a result for an athlete."""
    try:
        result = CompetitionResult.objects.create(
            competition_id=competition_id,
            athlete_id=payload.athlete_id,
            category_id=payload.category_id,
            round_id=payload.round_id,
            ranking=payload.ranking,
            attempts=payload.attempts,
            disqualified=payload.disqualified,
            disqualification_reason=payload.disqualification_reason
        )
        return 201, result
    except Exception as e:
        return 400, {"error": str(e)}

@router.get("/{competition_id}/results", response={200: List[ResultOut], 404: ErrorResponse})
def list_results(
    request, 
    competition_id: int, 
    round_id: Optional[int] = None,
    category_id: Optional[int] = None
):
    """List results for a competition with optional filtering."""
    results = CompetitionResult.objects.filter(competition_id=competition_id)
    if round_id:
        results = results.filter(round_id=round_id)
    if category_id:
        results = results.filter(category_id=category_id)
    return 200, results

@router.get("/{competition_id}/athlete/{athlete_id}/results", response={200: List[ResultOut], 404: ErrorResponse})
def get_athlete_results(request, competition_id: int, athlete_id: int):
    """Get all results for a specific athlete in a competition."""
    results = CompetitionResult.objects.filter(
        competition_id=competition_id,
        athlete_id=athlete_id
    ).order_by('round__order')
    return 200, results

# Appeals Management
@router.post("/{competition_id}/appeals", response={201: AppealOut, 400: ErrorResponse})
def submit_appeal(request, competition_id: int, payload: AppealIn):
    """Submit an appeal for a competition result."""
    try:
        appeal = Appeal.objects.create(
            competition_id=competition_id,
            athlete_id=payload.athlete_id,
            round_id=payload.round_id,
            problem_number=payload.problem_number,
            reason=payload.reason,
            evidence=payload.evidence
        )
        return 201, appeal
    except Exception as e:
        return 400, {"error": str(e)}

@router.get("/{competition_id}/appeals", response={200: List[AppealOut], 404: ErrorResponse})
def list_appeals(request, competition_id: int, status: Optional[str] = None):
    """List all appeals for a competition."""
    appeals = Appeal.objects.filter(competition_id=competition_id)
    if status:
        appeals = appeals.filter(status=status)
    return 200, appeals

@router.get("/ping", response={200: SuccessResponse})
def ping(request):
    """Test endpoint to verify router is mounted"""
    return 200, {"success": True, "message": "competitions router is responding"}

# Round Management
@router.post("/{competition_id}/rounds", response={201: RoundOut, 400: ErrorResponse})
@role_required(['Admin', 'Technical Delegate'])
def create_round(request, competition_id: int, payload: RoundIn):
    """Create a new round for a competition."""
    try:
        competition = get_object_or_404(Competition, id=competition_id)
        round = Round.objects.create(
            competition=competition,
            **payload.dict()
        )
        return 201, round
    except Exception as e:
        return 400, {"error": str(e)}

@router.get("/{competition_id}/rounds", response={200: List[RoundOut], 404: ErrorResponse})
def list_rounds(request, competition_id: int):
    """List all rounds for a competition."""
    rounds = Round.objects.filter(competition_id=competition_id).order_by('order')
    return 200, rounds

@router.get("/{competition_id}/rounds/{round_id}", response={200: RoundOut, 404: ErrorResponse})
def get_round(request, competition_id: int, round_id: int):
    """Get details of a specific round."""
    round = get_object_or_404(Round, competition_id=competition_id, id=round_id)
    return 200, round

# New Endpoints
@router.get("/search", response={200: List[CompetitionOut], 400: ErrorResponse})
def search_competitions(request, params: CompetitionSearchSchema = Query(...)):
    """
    Advanced search for competitions with multiple filter criteria.
    """
    try:
        cache_key = f"competition_search_{hash(frozenset(params.dict().items()))}"
        cached_results = cache.get(cache_key)
        
        if cached_results:
            return 200, cached_results

        query = Competition.objects.all()

        if params.query:
            query = query.filter(
                Q(name__icontains=params.query) |
                Q(description__icontains=params.query)
            )

        if params.league_id:
            query = query.filter(league_id=params.league_id)

        if params.status:
            query = query.filter(status=params.status)

        if params.start_date:
            query = query.filter(start_date__gte=params.start_date)

        if params.end_date:
            query = query.filter(end_date__lte=params.end_date)

        if params.location_city:
            query = query.filter(location__city__icontains=params.location_city)

        if params.category_id:
            query = query.filter(categories__id=params.category_id)

        if params.has_available_registration is not None:
            now = datetime.now()
            if params.has_available_registration:
                query = query.filter(
                    registration_deadline__gt=now,
                    start_date__gt=now
                )
            else:
                query = query.filter(
                    Q(registration_deadline__lte=now) |
                    Q(start_date__lte=now)
                )

        results = list(query.distinct())
        cache.set(cache_key, results, timeout=300)  # Cache for 5 minutes
        return 200, results
    except Exception as e:
        return 400, {"error": str(e)}

@router.get("/{competition_id}/overview", response={200: CompetitionOverviewSchema, 404: ErrorResponse})
def get_competition_overview(
    request,
    competition_id: int,
    include_events: bool = True,
    include_registrations: bool = True,
    include_results: bool = True
):
    """
    Get a comprehensive overview of a competition including events, registrations, and results.
    """
    try:
        cache_key = f"competition_overview_{competition_id}_{include_events}_{include_registrations}_{include_results}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return 200, cached_data

        competition = get_object_or_404(Competition, id=competition_id)
        overview = {
            "id": competition.id,
            "name": competition.name,
            "status": competition.status,
            "start_date": competition.start_date,
            "end_date": competition.end_date,
            "location": competition.location,
            "league": {
                "id": competition.league.id,
                "name": competition.league.name
            }
        }

        if include_events:
            overview["events"] = list(competition.event_set.all().values(
                'id', 'name', 'event_type', 'start_time', 'end_time',
                'status', 'location'
            ))

        if include_registrations:
            overview["registrations"] = [
                {
                    "athlete_id": reg["athlete__id"],
                    "athlete_first_name": reg["athlete__first_name"],
                    "athlete_last_name": reg["athlete__last_name"],
                    "category_name": reg["category__name"],
                    "waiver_signed": reg["waiver_signed"],
                    "medical_clearance": reg["medical_clearance"]
                }
                for reg in competition.competitionregistration_set.all()
                .select_related('athlete', 'category')
                .values(
                    'athlete__id', 'athlete__first_name', 'athlete__last_name',
                    'category__name', 'waiver_signed', 'medical_clearance'
                )
            ]

        if include_results:
            overview["results"] = [
                {
                    "athlete_id": res["athlete__id"],
                    "athlete_first_name": res["athlete__first_name"],
                    "athlete_last_name": res["athlete__last_name"],
                    "category_name": res["category__name"],
                    "ranking": res["ranking"],
                    "score": res["score"]
                }
                for res in competition.competitionresult_set.all()
                .select_related('athlete', 'category')
                .values(
                    'athlete__id', 'athlete__first_name', 'athlete__last_name',
                    'category__name', 'ranking', 'score'
                )
            ]

        cache.set(cache_key, overview, timeout=300)  # Cache for 5 minutes
        return 200, overview
    except Exception as e:
        return 404, {"error": str(e)}

@router.get("/{competition_id}/analytics", response=CompetitionAnalyticsSchema)
def get_competition_analytics(
    request,
    competition_id: int,
    category_id: Optional[int] = None
):
    """
    Get detailed analytics for a competition.
    """
    cache_key = f"competition_analytics_{competition_id}_{category_id}"
    cached_analytics = cache.get(cache_key)
    
    if cached_analytics:
        return cached_analytics

    competition = get_object_or_404(Competition, id=competition_id)
    registrations = CompetitionRegistration.objects.filter(competition=competition)
    results = CompetitionResult.objects.filter(competition=competition)
    appeals = Appeal.objects.filter(competition=competition)
    
    if category_id:
        registrations = registrations.filter(category_id=category_id)
        results = results.filter(category_id=category_id)

    analytics = {
        "total_registrations": registrations.count(),
        "registrations_by_category": dict(
            registrations.values('category__name')
            .annotate(count=Count('id'))
            .values_list('category__name', 'count')
        ),
        "average_score_by_category": dict(
            results.values('category__name')
            .annotate(avg_score=Avg('score'))
            .values_list('category__name', 'avg_score')
        ),
        "participation_trends": dict(
            registrations.values('created_at__date')
            .annotate(count=Count('id'))
            .values_list('created_at__date', 'count')
        ),
        "completion_rate": (
            results.count() / registrations.count()
            if registrations.count() > 0 else 0
        ),
        "appeal_statistics": {
            "total": appeals.count(),
            "pending": appeals.filter(status='pending').count(),
            "accepted": appeals.filter(status='accepted').count(),
            "rejected": appeals.filter(status='rejected').count()
        },
        "safety_incidents": dict(
            competition.eventincident_set.values('severity')
            .annotate(count=Count('id'))
            .values_list('severity', 'count')
        ),
        "performance_distribution": {}
    }

    # Calculate performance distribution by category
    for category in competition.categories.all():
        category_results = results.filter(category=category)
        if category_results.exists():
            analytics["performance_distribution"][category.name] = {
                "min_score": category_results.aggregate(Min('score'))['score__min'],
                "max_score": category_results.aggregate(Max('score'))['score__max'],
                "average_score": category_results.aggregate(Avg('score'))['score__avg'],
                "total_participants": category_results.count()
            }

    cache.set(cache_key, analytics, timeout=600)  # Cache for 10 minutes
    return analytics

@router.post("/bulk-schedule-update", response=Dict)
@role_required(['Admin', 'Technical Delegate'])
def bulk_update_competition_schedule(request, payload: BulkCompetitionScheduleUpdate):
    """
    Update the schedule of multiple competitions at once.
    """
    competitions = Competition.objects.filter(id__in=payload.competition_ids)
    updated_count = competitions.update(
        start_date=payload.start_date,
        end_date=payload.end_date
    )
    
    # Record schedule changes
    for competition in competitions:
        competition.eventschedulechange_set.create(
            changed_by=request.user,
            previous_start=competition.start_date,
            new_start=payload.start_date,
            previous_end=competition.end_date,
            new_end=payload.end_date,
            reason=payload.reason
        )
    
    # Clear relevant caches
    cache_keys_to_delete = [
        f"competition_search_*",
        f"competition_overview_*",
        f"competition_analytics_*"
    ]
    for key_pattern in cache_keys_to_delete:
        cache.delete_pattern(key_pattern)
    
    return {
        "success": True,
        "updated_count": updated_count,
        "message": f"Successfully updated schedule for {updated_count} competitions"
    } 