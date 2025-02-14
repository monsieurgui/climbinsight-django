from typing import List, Dict, Optional
from datetime import datetime, timedelta
from ninja import Router, Schema
from django.shortcuts import get_object_or_404
from .scheduling import ScheduleManager, TimeSlot
from .models import Competition
from .auth import CompetitionRoleAuth, require_competition_role

router = Router()
schedule_auth = CompetitionRoleAuth()

class EventScheduleSchema(Schema):
    event_type: str
    start_time: datetime
    end_time: datetime
    area_name: str
    capacity: int
    category_id: Optional[int] = None
    isolation_required: bool = False
    duration: timedelta = None

class ScheduleSuggestionSchema(Schema):
    event_type: str
    duration: timedelta
    capacity: int
    category_id: Optional[int] = None
    isolation_required: bool = False
    preferred_time_range: Optional[Dict] = None

class DateRangeSchema(Schema):
    start_date: datetime
    end_date: datetime

@router.post("/{competition_id}/schedule", auth=schedule_auth)
@require_competition_role(['Admin', 'Technical Delegate'])
def create_competition_schedule(request, competition_id: int, events: List[EventScheduleSchema]) -> Dict:
    """Create a schedule for multiple events in the competition."""
    competition = get_object_or_404(Competition, id=competition_id)
    schedule_manager = ScheduleManager(competition_id)
    
    success, conflicts = schedule_manager.create_schedule([event.dict() for event in events])
    
    if success:
        return {
            'status': 'success',
            'message': 'Schedule created successfully'
        }
    else:
        return {
            'status': 'error',
            'message': 'Schedule creation failed due to conflicts',
            'conflicts': [
                {
                    'type': conflict.type,
                    'time_slot': {
                        'start_time': conflict.time_slot.start_time,
                        'end_time': conflict.time_slot.end_time,
                        'area_name': conflict.time_slot.area_name,
                        'event_type': conflict.time_slot.event_type
                    },
                    'details': conflict.details
                }
                for conflict in conflicts
            ]
        }

@router.get("/{competition_id}/schedule", auth=schedule_auth)
def get_competition_schedule(request, competition_id: int, date: Optional[datetime] = None) -> Dict:
    """Get the competition schedule, optionally filtered by date."""
    competition = get_object_or_404(Competition, id=competition_id)
    schedule_manager = ScheduleManager(competition_id)
    return schedule_manager.get_schedule(date)

@router.post("/{competition_id}/schedule/suggest", auth=schedule_auth)
def suggest_schedule(request, competition_id: int, events: List[ScheduleSuggestionSchema]) -> List[Dict]:
    """Get schedule suggestions for a set of events."""
    competition = get_object_or_404(Competition, id=competition_id)
    schedule_manager = ScheduleManager(competition_id)
    
    return schedule_manager.suggest_schedule([
        {
            'event_type': event.event_type,
            'duration': event.duration,
            'capacity': event.capacity,
            'category_id': event.category_id,
            'isolation_required': event.isolation_required,
            'preferred_time_range': event.preferred_time_range
        }
        for event in events
    ])

@router.get("/{competition_id}/schedule/athlete/{athlete_id}", auth=schedule_auth)
def get_athlete_schedule(request, competition_id: int, athlete_id: int, 
                        date: Optional[datetime] = None) -> List[Dict]:
    """Get an athlete's schedule for the competition."""
    competition = get_object_or_404(Competition, id=competition_id)
    schedule_manager = ScheduleManager(competition_id)
    return schedule_manager.check_athlete_schedule(athlete_id, date)

@router.get("/{competition_id}/schedule/conflicts", auth=schedule_auth)
def check_schedule_conflicts(request, competition_id: int, 
                           date_range: DateRangeSchema) -> List[Dict]:
    """Check for scheduling conflicts within a date range."""
    competition = get_object_or_404(Competition, id=competition_id)
    schedule_manager = ScheduleManager(competition_id)
    
    # Get all events in the date range
    schedule = schedule_manager.get_schedule()
    events = []
    for area_events in schedule.values():
        for event in area_events:
            if (date_range.start_date <= event['start_time'] <= date_range.end_date or
                date_range.start_date <= event['end_time'] <= date_range.end_date):
                events.append(event)
    
    # Convert events to time slots and check conflicts
    time_slots = [
        TimeSlot(
            start_time=event['start_time'],
            end_time=event['end_time'],
            event_type=event['event_type'],
            area_name=event['area_name'],
            capacity=event['participants_count'],
            category_id=event.get('category_id')
        )
        for event in events
    ]
    
    all_conflicts = []
    for i, slot in enumerate(time_slots):
        conflicts = schedule_manager._check_conflicts(slot, time_slots[:i] + time_slots[i+1:])
        if conflicts:
            all_conflicts.extend(conflicts)
    
    return [
        {
            'type': conflict.type,
            'event_details': {
                'start_time': conflict.time_slot.start_time,
                'end_time': conflict.time_slot.end_time,
                'area_name': conflict.time_slot.area_name,
                'event_type': conflict.time_slot.event_type
            },
            'conflicting_event': {
                'start_time': conflict.conflicting_slot.start_time,
                'end_time': conflict.conflicting_slot.end_time,
                'area_name': conflict.conflicting_slot.area_name,
                'event_type': conflict.conflicting_slot.event_type
            } if conflict.conflicting_slot else None,
            'details': conflict.details
        }
        for conflict in all_conflicts
    ]

@router.get("/{competition_id}/schedule/availability", auth=schedule_auth)
def get_area_availability(request, competition_id: int, area_name: str,
                         date_range: DateRangeSchema) -> List[Dict]:
    """Get availability windows for an area within a date range."""
    competition = get_object_or_404(Competition, id=competition_id)
    schedule_manager = ScheduleManager(competition_id)
    
    # Get all events for the area
    schedule = schedule_manager.get_schedule()
    area_events = schedule.get(area_name, [])
    
    # Filter events within date range
    relevant_events = [
        event for event in area_events
        if (date_range.start_date <= event['start_time'] <= date_range.end_date or
            date_range.start_date <= event['end_time'] <= date_range.end_date)
    ]
    
    # Sort events by start time
    relevant_events.sort(key=lambda x: x['start_time'])
    
    # Find available windows
    available_windows = []
    current_time = date_range.start_date
    
    for event in relevant_events:
        if current_time < event['start_time']:
            available_windows.append({
                'start_time': current_time,
                'end_time': event['start_time'],
                'duration_minutes': int((event['start_time'] - current_time).total_seconds() / 60)
            })
        current_time = max(current_time, event['end_time'])
    
    # Add final window if needed
    if current_time < date_range.end_date:
        available_windows.append({
            'start_time': current_time,
            'end_time': date_range.end_date,
            'duration_minutes': int((date_range.end_date - current_time).total_seconds() / 60)
        })
    
    return available_windows 