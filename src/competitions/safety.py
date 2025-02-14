from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from django.core.cache import cache

class SafetyStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    PENDING = "pending"
    NEEDS_INSPECTION = "needs_inspection"

@dataclass
class SafetyCheck:
    """Represents a safety check requirement."""
    check_type: str
    description: str
    frequency: timedelta
    required_role: str
    checklist: List[str]
    documentation_required: bool = False

@dataclass
class SafetyIncident:
    """Represents a safety incident."""
    incident_type: str
    severity: str
    description: str
    location: Dict
    timestamp: datetime
    reported_by: str
    affected_areas: List[str]
    immediate_actions: List[str]
    status: str = "open"

class SafetyProtocolManager:
    """Manages safety protocols and checks for competitions."""
    
    def __init__(self, competition_id: int):
        self.competition_id = competition_id
        self.safety_checks: Dict[str, SafetyCheck] = self._initialize_safety_checks()
        
    def _initialize_safety_checks(self) -> Dict[str, SafetyCheck]:
        """Initialize standard safety checks for climbing competitions."""
        return {
            'route_inspection': SafetyCheck(
                check_type="route",
                description="Complete route safety inspection",
                frequency=timedelta(days=1),
                required_role="Route Setter",
                checklist=[
                    "All holds securely fastened",
                    "No loose bolts or hardware",
                    "Proper distance between routes",
                    "Fall zones clear and properly marked",
                    "Route difficulty correctly marked"
                ],
                documentation_required=True
            ),
            'equipment_inspection': SafetyCheck(
                check_type="equipment",
                description="Safety equipment inspection",
                frequency=timedelta(hours=4),
                required_role="Technical Delegate",
                checklist=[
                    "Ropes condition check",
                    "Harnesses inspection",
                    "Carabiners and quickdraws check",
                    "Belay devices inspection",
                    "Crash pads condition assessment"
                ],
                documentation_required=True
            ),
            'area_safety': SafetyCheck(
                check_type="area",
                description="Climbing area safety check",
                frequency=timedelta(hours=2),
                required_role="Safety Officer",
                checklist=[
                    "Proper padding placement",
                    "Emergency exits clear",
                    "First aid equipment accessible",
                    "Proper lighting",
                    "Ventilation working"
                ]
            ),
            'isolation_check': SafetyCheck(
                check_type="isolation",
                description="Isolation zone security check",
                frequency=timedelta(hours=1),
                required_role="Technical Delegate",
                checklist=[
                    "Access control working",
                    "Communication systems check",
                    "Proper athlete separation",
                    "Warmup facilities safe",
                    "Staff supervision in place"
                ]
            ),
            'emergency_systems': SafetyCheck(
                check_type="emergency",
                description="Emergency response systems check",
                frequency=timedelta(days=1),
                required_role="Safety Officer",
                checklist=[
                    "First aid kits complete",
                    "Emergency contacts updated",
                    "Communication devices working",
                    "Evacuation routes clear",
                    "Medical equipment check"
                ],
                documentation_required=True
            )
        }
    
    def perform_safety_check(self, check_type: str, location: str,
                           performed_by: str, notes: Optional[str] = None) -> Dict:
        """Perform a safety check and record results."""
        safety_check = self.safety_checks.get(check_type)
        if not safety_check:
            return {
                'status': 'error',
                'message': f'Unknown safety check type: {check_type}'
            }
        
        # Get last check timestamp from cache
        cache_key = f"safety_check_{self.competition_id}_{check_type}_{location}"
        last_check = cache.get(cache_key)
        
        if last_check and datetime.now() - last_check['timestamp'] < safety_check.frequency:
            return {
                'status': 'error',
                'message': f'Check not due yet. Next check due at {last_check["timestamp"] + safety_check.frequency}'
            }
        
        check_result = {
            'type': check_type,
            'location': location,
            'timestamp': datetime.now(),
            'performed_by': performed_by,
            'checklist_completed': True,
            'notes': notes,
            'status': SafetyStatus.PASSED.value
        }
        
        # Cache the check result
        cache.set(cache_key, check_result, timeout=int(safety_check.frequency.total_seconds()))
        
        return {
            'status': 'success',
            'message': 'Safety check completed successfully',
            'result': check_result
        }
    
    def report_incident(self, incident: SafetyIncident) -> Dict:
        """Report and handle a safety incident."""
        # Cache the incident
        cache_key = f"safety_incident_{self.competition_id}_{incident.timestamp.isoformat()}"
        cache.set(cache_key, incident.__dict__, timeout=86400)  # Cache for 24 hours
        
        # Trigger immediate safety checks for affected areas
        affected_checks = []
        for area in incident.affected_areas:
            for check_type, check in self.safety_checks.items():
                affected_checks.append(self.perform_safety_check(
                    check_type=check_type,
                    location=area,
                    performed_by=incident.reported_by,
                    notes=f"Emergency check due to incident: {incident.description}"
                ))
        
        return {
            'status': 'success',
            'message': 'Incident reported and handled',
            'incident_id': cache_key,
            'triggered_checks': affected_checks
        }
    
    def get_safety_status(self, location: Optional[str] = None) -> Dict:
        """Get current safety status for a location or the entire competition."""
        all_checks = {}
        
        for check_type in self.safety_checks:
            if location:
                cache_key = f"safety_check_{self.competition_id}_{check_type}_{location}"
                check = cache.get(cache_key)
                if check:
                    all_checks[check_type] = check
            else:
                # Get all locations' checks
                pattern = f"safety_check_{self.competition_id}_{check_type}_*"
                checks = cache.get_many([key for key in cache.keys(pattern)])
                all_checks[check_type] = list(checks.values())
        
        # Calculate overall status
        overall_status = SafetyStatus.PASSED.value
        for checks in all_checks.values():
            if isinstance(checks, list):
                for check in checks:
                    if check['status'] != SafetyStatus.PASSED.value:
                        overall_status = SafetyStatus.NEEDS_INSPECTION.value
                        break
            elif checks and checks['status'] != SafetyStatus.PASSED.value:
                overall_status = SafetyStatus.NEEDS_INSPECTION.value
                break
        
        return {
            'overall_status': overall_status,
            'checks': all_checks,
            'last_updated': datetime.now().isoformat()
        }
    
    def get_safety_requirements(self, event_type: str) -> Dict:
        """Get safety requirements for a specific event type."""
        requirements = {
            'lead_climbing': {
                'required_checks': ['route_inspection', 'equipment_inspection', 'area_safety'],
                'required_equipment': [
                    'Certified ropes',
                    'Harnesses',
                    'Quickdraws',
                    'Belay devices',
                    'First aid kit'
                ],
                'staff_requirements': [
                    {'role': 'Route Setter', 'count': 2},
                    {'role': 'Safety Officer', 'count': 1},
                    {'role': 'Medical Staff', 'count': 1}
                ]
            },
            'bouldering': {
                'required_checks': ['route_inspection', 'area_safety'],
                'required_equipment': [
                    'Crash pads',
                    'Brushes',
                    'First aid kit'
                ],
                'staff_requirements': [
                    {'role': 'Route Setter', 'count': 2},
                    {'role': 'Safety Officer', 'count': 1}
                ]
            },
            'speed_climbing': {
                'required_checks': [
                    'route_inspection',
                    'equipment_inspection',
                    'area_safety'
                ],
                'required_equipment': [
                    'Auto-belay devices',
                    'Harnesses',
                    'First aid kit',
                    'Timing system'
                ],
                'staff_requirements': [
                    {'role': 'Route Setter', 'count': 1},
                    {'role': 'Safety Officer', 'count': 1},
                    {'role': 'Technical Official', 'count': 2}
                ]
            }
        }
        
        return requirements.get(event_type, {
            'required_checks': ['area_safety'],
            'required_equipment': ['First aid kit'],
            'staff_requirements': [{'role': 'Safety Officer', 'count': 1}]
        })
    
    def validate_safety_setup(self, event_type: str, location: str) -> Dict:
        """Validate that all safety requirements are met for an event."""
        requirements = self.get_safety_requirements(event_type)
        status = self.get_safety_status(location)
        
        validation = {
            'passed': True,
            'checks': {},
            'missing_requirements': []
        }
        
        # Validate required checks
        for check_type in requirements['required_checks']:
            check_status = status['checks'].get(check_type, {}).get('status')
            validation['checks'][check_type] = check_status == SafetyStatus.PASSED.value
            if not validation['checks'][check_type]:
                validation['passed'] = False
                validation['missing_requirements'].append(
                    f"Safety check required: {check_type}"
                )
        
        return validation 