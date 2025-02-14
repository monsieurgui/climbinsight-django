from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class Area:
    """Represents a specific area within a venue."""
    name: str
    type: str  # climbing, isolation, warmup, medical, etc.
    capacity: int
    equipment: List[Dict]
    availability: Dict[str, List[datetime]]  # schedule of availability
    requirements: Dict  # specific requirements for the area

@dataclass
class Route:
    """Represents a climbing route in the venue."""
    identifier: str
    grade: str
    style: str
    height: float
    holds_count: int
    setter: str
    safety_requirements: Dict
    maintenance_history: List[Dict]

class VenueManager:
    """Manages venue areas, routes, and scheduling."""
    
    def __init__(self, competition_id: int):
        self.competition_id = competition_id
        self.areas: Dict[str, Area] = {}
        self.routes: Dict[str, Route] = {}
        self.schedule: Dict[str, List[Dict]] = {}
    
    def add_area(self, area: Area) -> bool:
        """Add a new area to the venue."""
        if area.name in self.areas:
            return False
        self.areas[area.name] = area
        self.schedule[area.name] = []
        return True
    
    def update_area(self, area_name: str, updates: Dict) -> bool:
        """Update an existing area's details."""
        if area_name not in self.areas:
            return False
        area = self.areas[area_name]
        for key, value in updates.items():
            setattr(area, key, value)
        return True
    
    def add_route(self, route: Route) -> bool:
        """Add a new route to the venue."""
        if route.identifier in self.routes:
            return False
        self.routes[route.identifier] = route
        return True
    
    def update_route(self, route_id: str, updates: Dict) -> bool:
        """Update an existing route's details."""
        if route_id not in self.routes:
            return False
        route = self.routes[route_id]
        for key, value in updates.items():
            setattr(route, key, value)
        return True
    
    def schedule_area(self, area_name: str, event_type: str, start_time: datetime, 
                     end_time: datetime, capacity_required: int) -> bool:
        """Schedule an area for a specific time period."""
        if area_name not in self.areas:
            return False
            
        area = self.areas[area_name]
        
        # Check capacity
        if capacity_required > area.capacity:
            return False
            
        # Check for conflicts
        for booking in self.schedule[area_name]:
            if (booking['start_time'] < end_time and 
                booking['end_time'] > start_time):
                return False
        
        # Add scheduling
        self.schedule[area_name].append({
            'event_type': event_type,
            'start_time': start_time,
            'end_time': end_time,
            'capacity_required': capacity_required
        })
        return True
    
    def get_area_schedule(self, area_name: str, date: datetime) -> List[Dict]:
        """Get the schedule for a specific area on a given date."""
        if area_name not in self.schedule:
            return []
            
        day_start = datetime.combine(date, datetime.min.time())
        day_end = day_start + timedelta(days=1)
        
        return [
            booking for booking in self.schedule[area_name]
            if booking['start_time'].date() == date.date()
        ]
    
    def get_available_times(self, area_name: str, duration: timedelta,
                          start_date: datetime, end_date: datetime) -> List[datetime]:
        """Find available time slots for an area."""
        if area_name not in self.areas:
            return []
            
        available_times = []
        current_time = start_date
        
        while current_time + duration <= end_date:
            is_available = True
            for booking in self.schedule[area_name]:
                if (current_time < booking['end_time'] and 
                    current_time + duration > booking['start_time']):
                    is_available = False
                    current_time = booking['end_time']
                    break
            
            if is_available:
                available_times.append(current_time)
                current_time += duration
            else:
                current_time += timedelta(minutes=30)
        
        return available_times
    
    def check_safety_requirements(self, area_name: str) -> Dict:
        """Check safety requirements for an area."""
        if area_name not in self.areas:
            return {'status': 'error', 'message': 'Area not found'}
            
        area = self.areas[area_name]
        requirements = area.requirements
        
        checks = {
            'capacity_check': True,
            'equipment_check': all(eq.get('status') == 'ready' for eq in area.equipment),
            'safety_equipment': all(
                req in [eq['type'] for eq in area.equipment]
                for req in requirements.get('required_safety_equipment', [])
            )
        }
        
        return {
            'status': 'ready' if all(checks.values()) else 'not_ready',
            'checks': checks
        }
    
    def get_route_status(self, route_id: str) -> Dict:
        """Get the current status of a route."""
        if route_id not in self.routes:
            return {'status': 'error', 'message': 'Route not found'}
            
        route = self.routes[route_id]
        last_maintenance = route.maintenance_history[-1] if route.maintenance_history else None
        
        return {
            'route_id': route_id,
            'grade': route.grade,
            'style': route.style,
            'last_maintenance': last_maintenance,
            'safety_status': 'ready' if self._check_route_safety(route) else 'needs_inspection'
        }
    
    def _check_route_safety(self, route: Route) -> bool:
        """Internal method to check route safety requirements."""
        if not route.maintenance_history:
            return False
            
        last_maintenance = route.maintenance_history[-1]
        maintenance_age = datetime.now() - last_maintenance['date']
        
        return (
            maintenance_age.days < route.safety_requirements.get('maintenance_interval_days', 7) and
            last_maintenance['status'] == 'passed'
        ) 