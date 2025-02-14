from ninja import Router, Schema
from typing import List, Optional, Dict
from datetime import datetime
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.db.models import Q

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