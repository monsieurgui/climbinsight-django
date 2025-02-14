from typing import List, Dict, Optional
from datetime import datetime
from ninja import Router, Schema
from django.shortcuts import get_object_or_404
from .staff import StaffManager, StaffAssignment, StaffRequirement, StaffRole
from .models import Competition
from .auth import CompetitionRoleAuth, require_competition_role

router = Router()
staff_auth = CompetitionRoleAuth()

class StaffAssignmentSchema(Schema):
    user_id: int
    role: str
    area: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    responsibilities: Optional[List[str]] = None
    backup_staff_id: Optional[int] = None

class StaffRequirementSchema(Schema):
    role: str
    count: int
    area: Optional[str] = None
    required_certifications: Optional[List[str]] = None
    required_experience: Optional[str] = None

class DateRangeSchema(Schema):
    start_date: datetime
    end_date: datetime

@router.post("/{competition_id}/staff/assign", auth=staff_auth)
@require_competition_role(['Admin', 'Technical Delegate'])
def assign_staff(request, competition_id: int, assignment: StaffAssignmentSchema) -> Dict:
    """Assign a staff member to a role."""
    competition = get_object_or_404(Competition, id=competition_id)
    staff_manager = StaffManager(competition_id)
    
    staff_assignment = StaffAssignment(
        user_id=assignment.user_id,
        role=StaffRole(assignment.role),
        area=assignment.area,
        start_time=assignment.start_time,
        end_time=assignment.end_time,
        responsibilities=assignment.responsibilities,
        backup_staff_id=assignment.backup_staff_id
    )
    
    return staff_manager.assign_staff(staff_assignment)

@router.delete("/{competition_id}/staff/assignment", auth=staff_auth)
@require_competition_role(['Admin', 'Technical Delegate'])
def remove_staff_assignment(request, competition_id: int, user_id: int,
                          role: str, area: Optional[str] = None) -> Dict:
    """Remove a staff assignment."""
    competition = get_object_or_404(Competition, id=competition_id)
    staff_manager = StaffManager(competition_id)
    return staff_manager.remove_assignment(user_id, StaffRole(role), area)

@router.get("/{competition_id}/staff/assignments", auth=staff_auth)
def list_staff_assignments(request, competition_id: int, role: Optional[str] = None,
                         area: Optional[str] = None) -> List[Dict]:
    """List all staff assignments, optionally filtered by role or area."""
    competition = get_object_or_404(Competition, id=competition_id)
    staff_manager = StaffManager(competition_id)
    return staff_manager.get_staff_assignments(
        role=StaffRole(role) if role else None,
        area=area
    )

@router.post("/{competition_id}/staff/validate", auth=staff_auth)
def validate_staffing(request, competition_id: int,
                     requirements: List[StaffRequirementSchema]) -> Dict:
    """Validate that all staffing requirements are met."""
    competition = get_object_or_404(Competition, id=competition_id)
    staff_manager = StaffManager(competition_id)
    
    staff_requirements = [
        StaffRequirement(
            role=StaffRole(req.role),
            count=req.count,
            area=req.area,
            required_certifications=req.required_certifications,
            required_experience=req.required_experience
        )
        for req in requirements
    ]
    
    return staff_manager.validate_staffing(staff_requirements)

@router.get("/{competition_id}/staff/schedule/{user_id}", auth=staff_auth)
def get_staff_schedule(request, competition_id: int, user_id: int,
                      date: Optional[datetime] = None) -> List[Dict]:
    """Get schedule for a specific staff member."""
    competition = get_object_or_404(Competition, id=competition_id)
    staff_manager = StaffManager(competition_id)
    return staff_manager.get_staff_schedule(user_id, date)

@router.get("/{competition_id}/staff/coverage/{area}", auth=staff_auth)
def get_area_coverage(request, competition_id: int, area: str,
                     date: Optional[datetime] = None) -> Dict:
    """Get staff coverage for a specific area."""
    competition = get_object_or_404(Competition, id=competition_id)
    staff_manager = StaffManager(competition_id)
    return staff_manager.get_area_coverage(area, date)

@router.get("/{competition_id}/staff/roles", auth=staff_auth)
def list_staff_roles(request, competition_id: int) -> List[Dict]:
    """List all available staff roles and their descriptions."""
    return [
        {
            'role': role.value,
            'description': {
                StaffRole.ADMIN: "Competition administrator with full access",
                StaffRole.TECHNICAL_DELEGATE: "Oversees technical aspects and safety",
                StaffRole.SAFETY_OFFICER: "Manages safety protocols and inspections",
                StaffRole.ROUTE_SETTER: "Designs and maintains climbing routes",
                StaffRole.JUDGE: "Evaluates athlete performances",
                StaffRole.MEDICAL_STAFF: "Provides medical support",
                StaffRole.ISOLATION_OFFICIAL: "Manages isolation zone",
                StaffRole.SCORING_OFFICIAL: "Manages scoring and results"
            }.get(role, "No description available")
        }
        for role in StaffRole
    ]

@router.get("/{competition_id}/staff/requirements/{event_type}", auth=staff_auth)
def get_event_staff_requirements(request, competition_id: int, event_type: str) -> List[Dict]:
    """Get staff requirements for a specific event type."""
    requirements = {
        'lead_climbing': [
            {'role': StaffRole.TECHNICAL_DELEGATE.value, 'count': 1},
            {'role': StaffRole.SAFETY_OFFICER.value, 'count': 2},
            {'role': StaffRole.ROUTE_SETTER.value, 'count': 2},
            {'role': StaffRole.JUDGE.value, 'count': 4},
            {'role': StaffRole.MEDICAL_STAFF.value, 'count': 1},
            {'role': StaffRole.ISOLATION_OFFICIAL.value, 'count': 2}
        ],
        'bouldering': [
            {'role': StaffRole.TECHNICAL_DELEGATE.value, 'count': 1},
            {'role': StaffRole.SAFETY_OFFICER.value, 'count': 1},
            {'role': StaffRole.ROUTE_SETTER.value, 'count': 3},
            {'role': StaffRole.JUDGE.value, 'count': 6},
            {'role': StaffRole.MEDICAL_STAFF.value, 'count': 1}
        ],
        'speed_climbing': [
            {'role': StaffRole.TECHNICAL_DELEGATE.value, 'count': 1},
            {'role': StaffRole.SAFETY_OFFICER.value, 'count': 1},
            {'role': StaffRole.ROUTE_SETTER.value, 'count': 1},
            {'role': StaffRole.JUDGE.value, 'count': 2},
            {'role': StaffRole.MEDICAL_STAFF.value, 'count': 1},
            {'role': StaffRole.SCORING_OFFICIAL.value, 'count': 2}
        ]
    }
    
    return requirements.get(event_type, [
        {'role': StaffRole.TECHNICAL_DELEGATE.value, 'count': 1},
        {'role': StaffRole.SAFETY_OFFICER.value, 'count': 1},
        {'role': StaffRole.JUDGE.value, 'count': 2}
    ])

@router.get("/{competition_id}/staff/summary", auth=staff_auth)
def get_staff_summary(request, competition_id: int) -> Dict:
    """Get a summary of staff assignments and coverage."""
    competition = get_object_or_404(Competition, id=competition_id)
    staff_manager = StaffManager(competition_id)
    
    all_assignments = staff_manager.get_staff_assignments()
    
    # Count staff by role
    role_counts = {}
    for assignment in all_assignments:
        role = assignment['role']
        role_counts[role] = role_counts.get(role, 0) + 1
    
    # Count staff by area
    area_counts = {}
    for assignment in all_assignments:
        if assignment.get('area'):
            area = assignment['area']
            area_counts[area] = area_counts.get(area, 0) + 1
    
    # Get current shift coverage
    current_time = datetime.now()
    current_staff = []
    for assignment in all_assignments:
        if (assignment.get('start_time') and assignment.get('end_time')):
            start_time = datetime.fromisoformat(assignment['start_time'])
            end_time = datetime.fromisoformat(assignment['end_time'])
            if start_time <= current_time <= end_time:
                current_staff.append({
                    'user_id': assignment['user_id'],
                    'role': assignment['role'],
                    'area': assignment.get('area')
                })
    
    return {
        'total_staff': len(set(a['user_id'] for a in all_assignments)),
        'staff_by_role': role_counts,
        'staff_by_area': area_counts,
        'current_shift': {
            'staff_count': len(current_staff),
            'staff': current_staff
        }
    } 