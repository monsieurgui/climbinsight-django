from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from django.core.cache import cache
from django.db.models import Q

from users.models import User
from .models import Competition

class StaffRole(Enum):
    ADMIN = "Admin"
    TECHNICAL_DELEGATE = "Technical Delegate"
    SAFETY_OFFICER = "Safety Officer"
    ROUTE_SETTER = "Route Setter"
    JUDGE = "Judge"
    MEDICAL_STAFF = "Medical Staff"
    ISOLATION_OFFICIAL = "Isolation Official"
    SCORING_OFFICIAL = "Scoring Official"

@dataclass
class StaffAssignment:
    """Represents a staff assignment."""
    user_id: int
    role: StaffRole
    area: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    responsibilities: List[str] = None
    backup_staff_id: Optional[int] = None

@dataclass
class StaffRequirement:
    """Represents staff requirements for an event or area."""
    role: StaffRole
    count: int
    area: Optional[str] = None
    required_certifications: List[str] = None
    required_experience: Optional[str] = None

class StaffManager:
    """Manages competition staff assignments and requirements."""
    
    def __init__(self, competition_id: int):
        self.competition_id = competition_id
        self.competition = Competition.objects.get(id=competition_id)
        
    def assign_staff(self, assignment: StaffAssignment) -> Dict:
        """Assign a staff member to a role."""
        # Validate user exists and has required role
        try:
            user = User.objects.get(id=assignment.user_id)
            if not user.has_role(assignment.role.value):
                return {
                    'status': 'error',
                    'message': f'User does not have required role: {assignment.role.value}'
                }
        except User.DoesNotExist:
            return {
                'status': 'error',
                'message': 'User not found'
            }
        
        # Check for conflicts if time-based assignment
        if assignment.start_time and assignment.end_time:
            conflicts = self._check_assignment_conflicts(assignment)
            if conflicts:
                return {
                    'status': 'error',
                    'message': 'Assignment conflicts detected',
                    'conflicts': conflicts
                }
        
        # Cache the assignment
        cache_key = f"staff_assignment_{self.competition_id}_{assignment.user_id}_{assignment.role.value}"
        if assignment.area:
            cache_key += f"_{assignment.area}"
        
        cache.set(cache_key, assignment.__dict__, timeout=86400)  # Cache for 24 hours
        
        return {
            'status': 'success',
            'message': 'Staff assigned successfully',
            'assignment': assignment.__dict__
        }
    
    def remove_assignment(self, user_id: int, role: StaffRole, area: Optional[str] = None) -> Dict:
        """Remove a staff assignment."""
        cache_key = f"staff_assignment_{self.competition_id}_{user_id}_{role.value}"
        if area:
            cache_key += f"_{area}"
        
        if cache.delete(cache_key):
            return {
                'status': 'success',
                'message': 'Assignment removed successfully'
            }
        return {
            'status': 'error',
            'message': 'Assignment not found'
        }
    
    def get_staff_assignments(self, role: Optional[StaffRole] = None,
                            area: Optional[str] = None) -> List[Dict]:
        """Get all staff assignments, optionally filtered by role or area."""
        pattern = f"staff_assignment_{self.competition_id}_*"
        assignment_keys = [key for key in cache.keys(pattern)]
        
        assignments = []
        for key in assignment_keys:
            assignment_data = cache.get(key)
            if assignment_data:
                if role and assignment_data['role'] != role.value:
                    continue
                if area and assignment_data.get('area') != area:
                    continue
                assignments.append(assignment_data)
        
        return assignments
    
    def validate_staffing(self, requirements: List[StaffRequirement]) -> Dict:
        """Validate that all staffing requirements are met."""
        validation = {
            'passed': True,
            'missing_requirements': [],
            'warnings': []
        }
        
        for requirement in requirements:
            assigned_staff = self.get_staff_assignments(
                role=requirement.role,
                area=requirement.area
            )
            
            if len(assigned_staff) < requirement.count:
                validation['passed'] = False
                validation['missing_requirements'].append({
                    'role': requirement.role.value,
                    'area': requirement.area,
                    'required': requirement.count,
                    'assigned': len(assigned_staff),
                    'missing': requirement.count - len(assigned_staff)
                })
        
        return validation
    
    def get_staff_schedule(self, user_id: int, date: Optional[datetime] = None) -> List[Dict]:
        """Get schedule for a specific staff member."""
        assignments = self.get_staff_assignments()
        
        user_schedule = []
        for assignment in assignments:
            if assignment['user_id'] != user_id:
                continue
                
            if date and assignment.get('start_time'):
                assignment_date = datetime.fromisoformat(assignment['start_time'])
                if assignment_date.date() != date.date():
                    continue
            
            user_schedule.append(assignment)
        
        return sorted(user_schedule,
                     key=lambda x: datetime.fromisoformat(x['start_time'])
                     if x.get('start_time') else datetime.max)
    
    def get_area_coverage(self, area: str, date: Optional[datetime] = None) -> Dict:
        """Get staff coverage for a specific area."""
        assignments = self.get_staff_assignments(area=area)
        
        coverage = {
            'area': area,
            'date': date.isoformat() if date else None,
            'staff_count': len(assignments),
            'roles_covered': {},
            'time_slots': {}
        }
        
        for assignment in assignments:
            role = assignment['role']
            coverage['roles_covered'][role] = coverage['roles_covered'].get(role, 0) + 1
            
            if assignment.get('start_time') and assignment.get('end_time'):
                start_time = datetime.fromisoformat(assignment['start_time'])
                end_time = datetime.fromisoformat(assignment['end_time'])
                
                if date and start_time.date() != date.date():
                    continue
                
                time_key = f"{start_time.isoformat()}-{end_time.isoformat()}"
                if time_key not in coverage['time_slots']:
                    coverage['time_slots'][time_key] = {
                        'start': start_time.isoformat(),
                        'end': end_time.isoformat(),
                        'staff': []
                    }
                coverage['time_slots'][time_key]['staff'].append({
                    'user_id': assignment['user_id'],
                    'role': role
                })
        
        return coverage
    
    def _check_assignment_conflicts(self, assignment: StaffAssignment) -> List[Dict]:
        """Check for conflicts with existing assignments."""
        conflicts = []
        existing_assignments = self.get_staff_assignments()
        
        for existing in existing_assignments:
            if (existing['user_id'] == assignment.user_id and
                existing.get('start_time') and existing.get('end_time')):
                
                existing_start = datetime.fromisoformat(existing['start_time'])
                existing_end = datetime.fromisoformat(existing['end_time'])
                
                if (assignment.start_time < existing_end and
                    assignment.end_time > existing_start):
                    conflicts.append({
                        'type': 'time_overlap',
                        'existing_assignment': existing,
                        'conflicting_period': {
                            'start': max(assignment.start_time, existing_start).isoformat(),
                            'end': min(assignment.end_time, existing_end).isoformat()
                        }
                    })
        
        return conflicts 