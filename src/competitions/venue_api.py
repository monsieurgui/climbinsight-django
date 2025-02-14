from typing import List, Dict, Optional
from datetime import datetime, timedelta
from ninja import Router, Schema
from ninja.security import django_auth
from django.shortcuts import get_object_or_404
from .venues import Area, Route, VenueManager
from .models import Competition
from .auth import CompetitionRoleAuth, require_competition_role

router = Router()
venue_auth = CompetitionRoleAuth()

class AreaSchema(Schema):
    name: str
    type: str
    capacity: int
    equipment: List[Dict]
    availability: Dict[str, List[datetime]]
    requirements: Dict

class RouteSchema(Schema):
    identifier: str
    grade: str
    style: str
    height: float
    holds_count: int
    setter: str
    safety_requirements: Dict

class ScheduleRequestSchema(Schema):
    area_name: str
    event_type: str
    start_time: datetime
    end_time: datetime
    capacity_required: int

class AvailabilityRequestSchema(Schema):
    area_name: str
    duration_minutes: int
    start_date: datetime
    end_date: datetime

@router.get("/{competition_id}/areas", auth=venue_auth)
def list_areas(request, competition_id: int) -> List[Dict]:
    """List all areas in the venue."""
    competition = get_object_or_404(Competition, id=competition_id)
    venue_manager = VenueManager(competition_id)
    return [
        {
            'name': area.name,
            'type': area.type,
            'capacity': area.capacity,
            'equipment_count': len(area.equipment),
            'safety_status': venue_manager.check_safety_requirements(area.name)
        }
        for area in venue_manager.areas.values()
    ]

@router.post("/{competition_id}/areas", auth=venue_auth)
@require_competition_role(['Admin', 'Technical Delegate'])
def create_area(request, competition_id: int, area_data: AreaSchema) -> Dict:
    """Create a new area in the venue."""
    competition = get_object_or_404(Competition, id=competition_id)
    venue_manager = VenueManager(competition_id)
    
    area = Area(**area_data.dict())
    if venue_manager.add_area(area):
        return {'status': 'success', 'message': 'Area created successfully'}
    return {'status': 'error', 'message': 'Area already exists'}

@router.put("/{competition_id}/areas/{area_name}", auth=venue_auth)
@require_competition_role(['Admin', 'Technical Delegate'])
def update_area(request, competition_id: int, area_name: str, updates: Dict) -> Dict:
    """Update an existing area."""
    competition = get_object_or_404(Competition, id=competition_id)
    venue_manager = VenueManager(competition_id)
    
    if venue_manager.update_area(area_name, updates):
        return {'status': 'success', 'message': 'Area updated successfully'}
    return {'status': 'error', 'message': 'Area not found'}

@router.get("/{competition_id}/routes", auth=venue_auth)
def list_routes(request, competition_id: int) -> List[Dict]:
    """List all routes in the venue."""
    competition = get_object_or_404(Competition, id=competition_id)
    venue_manager = VenueManager(competition_id)
    return [
        venue_manager.get_route_status(route_id)
        for route_id in venue_manager.routes
    ]

@router.post("/{competition_id}/routes", auth=venue_auth)
@require_competition_role(['Admin', 'Technical Delegate', 'Route Setter'])
def create_route(request, competition_id: int, route_data: RouteSchema) -> Dict:
    """Create a new route in the venue."""
    competition = get_object_or_404(Competition, id=competition_id)
    venue_manager = VenueManager(competition_id)
    
    route = Route(**route_data.dict(), maintenance_history=[])
    if venue_manager.add_route(route):
        return {'status': 'success', 'message': 'Route created successfully'}
    return {'status': 'error', 'message': 'Route already exists'}

@router.put("/{competition_id}/routes/{route_id}", auth=venue_auth)
@require_competition_role(['Admin', 'Technical Delegate', 'Route Setter'])
def update_route(request, competition_id: int, route_id: str, updates: Dict) -> Dict:
    """Update an existing route."""
    competition = get_object_or_404(Competition, id=competition_id)
    venue_manager = VenueManager(competition_id)
    
    if venue_manager.update_route(route_id, updates):
        return {'status': 'success', 'message': 'Route updated successfully'}
    return {'status': 'error', 'message': 'Route not found'}

@router.post("/{competition_id}/schedule", auth=venue_auth)
@require_competition_role(['Admin', 'Technical Delegate'])
def schedule_area(request, competition_id: int, schedule_data: ScheduleRequestSchema) -> Dict:
    """Schedule an area for a specific time period."""
    competition = get_object_or_404(Competition, id=competition_id)
    venue_manager = VenueManager(competition_id)
    
    if venue_manager.schedule_area(**schedule_data.dict()):
        return {'status': 'success', 'message': 'Area scheduled successfully'}
    return {'status': 'error', 'message': 'Scheduling failed - check capacity and conflicts'}

@router.get("/{competition_id}/schedule/{area_name}", auth=venue_auth)
def get_area_schedule(request, competition_id: int, area_name: str, date: datetime) -> List[Dict]:
    """Get the schedule for a specific area on a given date."""
    competition = get_object_or_404(Competition, id=competition_id)
    venue_manager = VenueManager(competition_id)
    return venue_manager.get_area_schedule(area_name, date)

@router.post("/{competition_id}/availability", auth=venue_auth)
def get_available_times(request, competition_id: int, 
                       availability_data: AvailabilityRequestSchema) -> List[datetime]:
    """Find available time slots for an area."""
    competition = get_object_or_404(Competition, id=competition_id)
    venue_manager = VenueManager(competition_id)
    
    duration = timedelta(minutes=availability_data.duration_minutes)
    return venue_manager.get_available_times(
        availability_data.area_name,
        duration,
        availability_data.start_date,
        availability_data.end_date
    )

@router.get("/{competition_id}/safety/{area_name}", auth=venue_auth)
def check_area_safety(request, competition_id: int, area_name: str) -> Dict:
    """Check safety requirements for an area."""
    competition = get_object_or_404(Competition, id=competition_id)
    venue_manager = VenueManager(competition_id)
    return venue_manager.check_safety_requirements(area_name)

@router.get("/{competition_id}/routes/{route_id}/status", auth=venue_auth)
def get_route_status(request, competition_id: int, route_id: str) -> Dict:
    """Get the current status of a route."""
    competition = get_object_or_404(Competition, id=competition_id)
    venue_manager = VenueManager(competition_id)
    return venue_manager.get_route_status(route_id) 