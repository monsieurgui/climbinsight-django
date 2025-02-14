from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from django.core.cache import cache

from .venues import VenueManager
from .models import Competition, CompetitionRegistration
from events.models import Event, EventParticipation

@dataclass
class TimeSlot:
    """Represents a time slot in the schedule."""
    start_time: datetime
    end_time: datetime
    event_type: str
    area_name: str
    capacity: int
    category_id: Optional[int] = None

@dataclass
class ScheduleConflict:
    """Represents a scheduling conflict."""
    type: str  # 'overlap', 'capacity', 'area_unavailable'
    time_slot: TimeSlot
    conflicting_slot: Optional[TimeSlot] = None
    details: Optional[Dict] = None

class ScheduleManager:
    """Manages competition schedules."""
    
    def __init__(self, competition_id: int):
        self.competition_id = competition_id
        self.venue_manager = VenueManager(competition_id)
        
    def create_schedule(self, events: List[Dict]) -> Tuple[bool, List[ScheduleConflict]]:
        """Create a schedule for multiple events."""
        conflicts = []
        scheduled_slots = []
        
        # Sort events by priority and constraints
        sorted_events = self._sort_events_by_priority(events)
        
        for event in sorted_events:
            time_slot = TimeSlot(
                start_time=event['start_time'],
                end_time=event['end_time'],
                event_type=event['event_type'],
                area_name=event['area_name'],
                capacity=event['capacity'],
                category_id=event.get('category_id')
            )
            
            # Check for conflicts
            slot_conflicts = self._check_conflicts(time_slot, scheduled_slots)
            if slot_conflicts:
                conflicts.extend(slot_conflicts)
                continue
            
            # Try to schedule the event
            if self._schedule_time_slot(time_slot):
                scheduled_slots.append(time_slot)
            else:
                conflicts.append(ScheduleConflict(
                    type='area_unavailable',
                    time_slot=time_slot,
                    details={'reason': 'Failed to schedule in venue'}
                ))
        
        return len(conflicts) == 0, conflicts
    
    def get_schedule(self, date: Optional[datetime] = None) -> Dict[str, List[Dict]]:
        """Get the schedule for a specific date or the entire competition."""
        cache_key = f"competition_schedule_{self.competition_id}_{date.date() if date else 'all'}"
        cached_schedule = cache.get(cache_key)
        
        if cached_schedule:
            return cached_schedule
            
        events = Event.objects.filter(competition_id=self.competition_id)
        if date:
            events = events.filter(start_time__date=date.date())
        
        schedule = {}
        for event in events:
            area_name = event.location['area']
            if area_name not in schedule:
                schedule[area_name] = []
            
            schedule[area_name].append({
                'event_id': event.id,
                'name': event.name,
                'event_type': event.event_type,
                'start_time': event.start_time,
                'end_time': event.end_time,
                'category_id': event.categories.first().id if event.categories.exists() else None,
                'isolation_required': bool(event.isolation_start),
                'participants_count': event.participants.count(),
                'status': event.status
            })
        
        # Cache for 5 minutes
        cache.set(cache_key, schedule, timeout=300)
        
        return schedule
    
    def suggest_schedule(self, events: List[Dict]) -> List[Dict]:
        """Suggest an optimal schedule for events."""
        suggested_schedule = []
        available_areas = list(self.venue_manager.areas.keys())
        
        for event in events:
            # Find best time slot for each event
            best_slot = self._find_optimal_time_slot(
                event_type=event['event_type'],
                duration=event['duration'],
                capacity_needed=event['capacity'],
                category_id=event.get('category_id'),
                available_areas=available_areas
            )
            
            if best_slot:
                suggested_schedule.append({
                    **event,
                    'start_time': best_slot.start_time,
                    'end_time': best_slot.end_time,
                    'area_name': best_slot.area_name
                })
        
        return suggested_schedule
    
    def check_athlete_schedule(self, athlete_id: int, date: Optional[datetime] = None) -> List[Dict]:
        """Get an athlete's schedule for a specific date or the entire competition."""
        participations = EventParticipation.objects.filter(
            event__competition_id=self.competition_id,
            athlete_id=athlete_id
        ).select_related('event')
        
        if date:
            participations = participations.filter(event__start_time__date=date.date())
        
        schedule = []
        for participation in participations:
            event = participation.event
            schedule.append({
                'event_id': event.id,
                'name': event.name,
                'event_type': event.event_type,
                'start_time': event.start_time,
                'end_time': event.end_time,
                'location': event.location,
                'starting_position': participation.starting_position,
                'isolation_time': event.isolation_start,
                'reporting_time': event.start_time - timedelta(minutes=30)
            })
        
        return sorted(schedule, key=lambda x: x['start_time'])
    
    def _sort_events_by_priority(self, events: List[Dict]) -> List[Dict]:
        """Sort events by priority and constraints."""
        def priority_key(event):
            priority = 0
            # Qualification rounds should be earlier
            if 'qualification' in event['event_type'].lower():
                priority += 100
            # Events with isolation periods need priority
            if event.get('isolation_required'):
                priority += 50
            # Events with more participants need larger time blocks
            priority += event.get('capacity', 0)
            return -priority  # Negative for descending order
            
        return sorted(events, key=priority_key)
    
    def _check_conflicts(self, time_slot: TimeSlot, existing_slots: List[TimeSlot]) -> List[ScheduleConflict]:
        """Check for scheduling conflicts."""
        conflicts = []
        
        for existing in existing_slots:
            # Check for time overlaps
            if (time_slot.start_time < existing.end_time and 
                time_slot.end_time > existing.start_time):
                # If same category, it's a direct conflict
                if time_slot.category_id and time_slot.category_id == existing.category_id:
                    conflicts.append(ScheduleConflict(
                        type='overlap',
                        time_slot=time_slot,
                        conflicting_slot=existing,
                        details={'reason': 'Category time overlap'}
                    ))
                # If same area, check capacity
                elif time_slot.area_name == existing.area_name:
                    area = self.venue_manager.areas.get(time_slot.area_name)
                    if area and (time_slot.capacity + existing.capacity) > area.capacity:
                        conflicts.append(ScheduleConflict(
                            type='capacity',
                            time_slot=time_slot,
                            conflicting_slot=existing,
                            details={'area_capacity': area.capacity}
                        ))
        
        return conflicts
    
    def _schedule_time_slot(self, time_slot: TimeSlot) -> bool:
        """Attempt to schedule a time slot in the venue."""
        return self.venue_manager.schedule_area(
            area_name=time_slot.area_name,
            event_type=time_slot.event_type,
            start_time=time_slot.start_time,
            end_time=time_slot.end_time,
            capacity_required=time_slot.capacity
        )
    
    def _find_optimal_time_slot(self, event_type: str, duration: timedelta,
                              capacity_needed: int, category_id: Optional[int],
                              available_areas: List[str]) -> Optional[TimeSlot]:
        """Find the optimal time slot for an event."""
        best_slot = None
        min_conflicts = float('inf')
        
        for area_name in available_areas:
            area = self.venue_manager.areas.get(area_name)
            if not area or area.capacity < capacity_needed:
                continue
                
            # Get available times for the area
            available_times = self.venue_manager.get_available_times(
                area_name=area_name,
                duration=duration,
                start_time=datetime.now(),  # Or competition start time
                end_time=datetime.now() + timedelta(days=7)  # Or competition end time
            )
            
            for start_time in available_times:
                slot = TimeSlot(
                    start_time=start_time,
                    end_time=start_time + duration,
                    event_type=event_type,
                    area_name=area_name,
                    capacity=capacity_needed,
                    category_id=category_id
                )
                
                # Count potential conflicts
                conflicts = len(self._check_conflicts(slot, []))
                if conflicts < min_conflicts:
                    min_conflicts = conflicts
                    best_slot = slot
                    if conflicts == 0:
                        break
            
            if best_slot and min_conflicts == 0:
                break
        
        return best_slot 