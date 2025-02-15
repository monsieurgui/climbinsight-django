from ninja import Router, Schema, Query
from typing import List, Optional, Dict
from datetime import datetime
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.db.models import Q, Count, Avg, Max, Min

from .models import Event, EventParticipation, EventIncident, EventScheduleChange
from users.decorators import role_required

router = Router()

# Schemas
class LocationSchema(Schema):
    area: str
    section: str
    details: Optional[Dict] = None
    equipment_requirements: Optional[Dict] = None

class RouteInfoSchema(Schema):
    grade: str
    style: str
    height: Optional[float] = None
    holds_count: Optional[int] = None
    setter_notes: Optional[str] = None
    safety_notes: Optional[str] = None

class EventBase(Schema):
    name: str
    event_type: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    isolation_start: Optional[datetime] = None
    isolation_end: Optional[datetime] = None
    location: LocationSchema
    route_info: Optional[RouteInfoSchema] = None
    categories: List[int]
    scoring_rules: Dict
    safety_requirements: Dict

class EventOut(EventBase):
    id: int
    competition_id: int
    status: str
    is_active: bool
    starting_order: Optional[Dict] = None
    created_at: datetime
    updated_at: datetime

class EventCreate(EventBase):
    competition_id: int

class EventUpdate(EventBase):
    pass

class ParticipationSchema(Schema):
    athlete_id: int
    category_id: int
    starting_position: Optional[int] = None

class IncidentSchema(Schema):
    incident_time: datetime
    incident_type: str
    description: str
    severity: str

class ScheduleChangeSchema(Schema):
    new_start: datetime
    new_end: datetime
    reason: str

# New Schemas
class EventSearchSchema(Schema):
    query: Optional[str] = None
    competition_id: Optional[int] = None
    event_type: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    category_id: Optional[int] = None
    status: Optional[str] = None

class EventAnalyticsSchema(Schema):
    total_participants: int
    participants_by_category: Dict[str, int]
    incidents_by_severity: Dict[str, int]
    schedule_changes: List[Dict]
    participation_rate: float
    average_duration: float
    status_distribution: Dict[str, int]

# Event Management Endpoints
@router.get("/competition/{competition_id}/events", response=List[EventOut])
def list_events(request, competition_id: int, event_type: Optional[str] = None):
    """List all events for a competition."""
    events = Event.objects.filter(competition_id=competition_id)
    if event_type:
        events = events.filter(event_type=event_type)
    return events.order_by('start_time')

@router.get("/events/{event_id}", response=EventOut)
def get_event(request, event_id: int):
    """Get detailed information about a specific event."""
    return get_object_or_404(Event, id=event_id)

@router.post("/competition/{competition_id}/events", response=EventOut)
@role_required(['Admin', 'Technical Delegate'])
def create_event(request, competition_id: int, payload: EventCreate):
    """Create a new event."""
    event = Event.objects.create(
        competition_id=competition_id,
        name=payload.name,
        event_type=payload.event_type,
        description=payload.description,
        start_time=payload.start_time,
        end_time=payload.end_time,
        isolation_start=payload.isolation_start,
        isolation_end=payload.isolation_end,
        location=payload.location.dict(),
        route_info=payload.route_info.dict() if payload.route_info else None,
        scoring_rules=payload.scoring_rules,
        safety_requirements=payload.safety_requirements
    )
    if payload.categories:
        event.categories.set(payload.categories)
    return event

@router.put("/events/{event_id}", response=EventOut)
@role_required(['Admin', 'Technical Delegate'])
def update_event(request, event_id: int, payload: EventUpdate):
    """Update event details."""
    event = get_object_or_404(Event, id=event_id)
    for attr, value in payload.dict(exclude_unset=True).items():
        if attr == 'categories':
            event.categories.set(value)
        elif attr in ['location', 'route_info']:
            setattr(event, attr, value.dict() if value else {})
        else:
            setattr(event, attr, value)
    event.save()
    return event

@router.delete("/events/{event_id}")
@role_required(['Admin'])
def delete_event(request, event_id: int):
    """Delete an event."""
    event = get_object_or_404(Event, id=event_id)
    event.delete()
    return {"success": True}

# Participation Management
@router.post("/events/{event_id}/participants", response=dict)
@role_required(['Admin', 'Technical Delegate', 'Official'])
def add_participant(request, event_id: int, payload: ParticipationSchema):
    """Add a participant to an event."""
    participation = EventParticipation.objects.create(
        event_id=event_id,
        athlete_id=payload.athlete_id,
        category_id=payload.category_id,
        starting_position=payload.starting_position
    )
    return {"success": True, "participation_id": participation.id}

@router.get("/events/{event_id}/participants", response=List[dict])
def list_participants(request, event_id: int, category_id: Optional[int] = None):
    """List all participants in an event."""
    participations = EventParticipation.objects.filter(event_id=event_id)
    if category_id:
        participations = participations.filter(category_id=category_id)
    return participations.order_by('category', 'starting_position')

# Starting Order Management
@router.post("/events/{event_id}/starting-order", response=dict)
@role_required(['Admin', 'Technical Delegate'])
def set_starting_order(request, event_id: int, category_id: int, order: List[int]):
    """Set the starting order for athletes in a category."""
    event = get_object_or_404(Event, id=event_id)
    
    # Update starting positions
    for position, athlete_id in enumerate(order, 1):
        EventParticipation.objects.filter(
            event=event,
            category_id=category_id,
            athlete_id=athlete_id
        ).update(starting_position=position)
    
    # Update event's starting order
    if not event.starting_order:
        event.starting_order = {}
    event.starting_order[str(category_id)] = order
    event.save()
    
    return {"success": True}

# Incident Management
@router.post("/events/{event_id}/incidents", response=dict)
@role_required(['Admin', 'Technical Delegate', 'Official', 'Medical Staff'])
def report_incident(request, event_id: int, payload: IncidentSchema):
    """Report an incident during an event."""
    incident = EventIncident.objects.create(
        event_id=event_id,
        reported_by=request.user,
        incident_time=payload.incident_time,
        incident_type=payload.incident_type,
        description=payload.description,
        severity=payload.severity
    )
    return {"success": True, "incident_id": incident.id}

@router.get("/events/{event_id}/incidents", response=List[dict])
@role_required(['Admin', 'Technical Delegate', 'Official', 'Medical Staff'])
def list_incidents(request, event_id: int):
    """List all incidents for an event."""
    return EventIncident.objects.filter(event_id=event_id).order_by('-incident_time')

# Schedule Management
@router.post("/events/{event_id}/schedule-change", response=dict)
@role_required(['Admin', 'Technical Delegate'])
def change_schedule(request, event_id: int, payload: ScheduleChangeSchema):
    """Change the schedule of an event."""
    event = get_object_or_404(Event, id=event_id)
    
    # Record the schedule change
    schedule_change = EventScheduleChange.objects.create(
        event=event,
        changed_by=request.user,
        previous_start=event.start_time,
        new_start=payload.new_start,
        previous_end=event.end_time,
        new_end=payload.new_end,
        reason=payload.reason
    )
    
    # Update event times
    event.start_time = payload.new_start
    event.end_time = payload.new_end
    event.save()
    
    return {
        "success": True,
        "schedule_change_id": schedule_change.id,
        "notification_required": True
    }

@router.get("/events/{event_id}/schedule-changes", response=List[dict])
def list_schedule_changes(request, event_id: int):
    """List all schedule changes for an event."""
    return EventScheduleChange.objects.filter(event_id=event_id).order_by('-created_at')

# New Endpoints
@router.get("/search", response=List[EventOut])
def search_events(request, params: EventSearchSchema = Query(...)):
    """
    Advanced search for events with multiple filter criteria.
    """
    cache_key = f"event_search_{hash(frozenset(params.dict().items()))}"
    cached_results = cache.get(cache_key)
    
    if cached_results:
        return cached_results

    query = Event.objects.all()

    if params.query:
        query = query.filter(
            Q(name__icontains=params.query) |
            Q(description__icontains=params.query)
        )

    if params.competition_id:
        query = query.filter(competition_id=params.competition_id)

    if params.event_type:
        query = query.filter(event_type=params.event_type)

    if params.start_date:
        query = query.filter(start_time__gte=params.start_date)

    if params.end_date:
        query = query.filter(end_time__lte=params.end_date)

    if params.category_id:
        query = query.filter(categories__id=params.category_id)

    if params.status:
        query = query.filter(status=params.status)

    results = list(query.distinct())
    cache.set(cache_key, results, timeout=300)  # Cache for 5 minutes
    return results

@router.get("/{event_id}/analytics", response=EventAnalyticsSchema)
def get_event_analytics(request, event_id: int):
    """
    Get detailed analytics for an event.
    """
    cache_key = f"event_analytics_{event_id}"
    cached_analytics = cache.get(cache_key)
    
    if cached_analytics:
        return cached_analytics

    event = get_object_or_404(Event, id=event_id)
    participations = event.eventparticipation_set.all()
    incidents = event.eventincident_set.all()
    schedule_changes = event.eventschedulechange_set.all()

    analytics = {
        "total_participants": participations.count(),
        "participants_by_category": dict(
            participations.values('category__name')
            .annotate(count=Count('id'))
            .values_list('category__name', 'count')
        ),
        "incidents_by_severity": dict(
            incidents.values('severity')
            .annotate(count=Count('id'))
            .values_list('severity', 'count')
        ),
        "schedule_changes": list(schedule_changes.values(
            'new_start', 'new_end', 'reason', 'created_at'
        )),
        "participation_rate": (
            participations.count() / event.competition.competitionregistration_set.count()
            if event.competition.competitionregistration_set.count() > 0 else 0
        ),
        "average_duration": (
            event.end_time - event.start_time
        ).total_seconds() / 3600,  # Convert to hours
        "status_distribution": dict(
            participations.values('status')
            .annotate(count=Count('id'))
            .values_list('status', 'count')
        )
    }

    cache.set(cache_key, analytics, timeout=600)  # Cache for 10 minutes
    return analytics

@router.get("/competition/{competition_id}/schedule", response=Dict)
def get_competition_schedule(
    request,
    competition_id: int,
    include_participants: bool = False,
    include_incidents: bool = False
):
    """
    Get a detailed schedule of all events in a competition.
    """
    cache_key = f"competition_schedule_{competition_id}_{include_participants}_{include_incidents}"
    cached_schedule = cache.get(cache_key)
    
    if cached_schedule:
        return cached_schedule

    events = Event.objects.filter(competition_id=competition_id).order_by('start_time')
    schedule = []

    for event in events:
        event_data = {
            "id": event.id,
            "name": event.name,
            "event_type": event.event_type,
            "start_time": event.start_time,
            "end_time": event.end_time,
            "location": event.location,
            "status": event.status,
            "categories": list(event.categories.values('id', 'name'))
        }

        if include_participants:
            event_data["participants"] = list(
                event.eventparticipation_set.select_related('athlete')
                .values('athlete__id', 'athlete__first_name', 'athlete__last_name',
                       'starting_position', 'status')
            )

        if include_incidents:
            event_data["incidents"] = list(
                event.eventincident_set.values('incident_type', 'severity',
                                             'incident_time', 'description')
            )

        schedule.append(event_data)

    result = {
        "competition_id": competition_id,
        "events": schedule,
        "total_events": len(schedule),
        "date_range": {
            "start": min(event.start_time for event in events),
            "end": max(event.end_time for event in events)
        }
    }

    cache.set(cache_key, result, timeout=300)  # Cache for 5 minutes
    return result 