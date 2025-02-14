from typing import List, Dict, Optional
from datetime import datetime
from ninja import Router, Schema
from django.shortcuts import get_object_or_404
from .safety import SafetyProtocolManager, SafetyIncident, SafetyStatus
from .models import Competition
from .auth import CompetitionRoleAuth, require_competition_role

router = Router()
safety_auth = CompetitionRoleAuth()

class SafetyCheckRequest(Schema):
    check_type: str
    location: str
    notes: Optional[str] = None

class SafetyIncidentReport(Schema):
    incident_type: str
    severity: str
    description: str
    location: Dict
    affected_areas: List[str]
    immediate_actions: List[str]

class SafetyRequirementQuery(Schema):
    event_type: str
    location: str

@router.post("/{competition_id}/safety/check", auth=safety_auth)
@require_competition_role(['Admin', 'Technical Delegate', 'Safety Officer', 'Route Setter'])
def perform_safety_check(request, competition_id: int, check_data: SafetyCheckRequest) -> Dict:
    """Perform a safety check and record results."""
    competition = get_object_or_404(Competition, id=competition_id)
    safety_manager = SafetyProtocolManager(competition_id)
    
    return safety_manager.perform_safety_check(
        check_type=check_data.check_type,
        location=check_data.location,
        performed_by=request.user.username,
        notes=check_data.notes
    )

@router.post("/{competition_id}/safety/incident", auth=safety_auth)
def report_safety_incident(request, competition_id: int, incident_data: SafetyIncidentReport) -> Dict:
    """Report a safety incident."""
    competition = get_object_or_404(Competition, id=competition_id)
    safety_manager = SafetyProtocolManager(competition_id)
    
    incident = SafetyIncident(
        incident_type=incident_data.incident_type,
        severity=incident_data.severity,
        description=incident_data.description,
        location=incident_data.location,
        timestamp=datetime.now(),
        reported_by=request.user.username,
        affected_areas=incident_data.affected_areas,
        immediate_actions=incident_data.immediate_actions
    )
    
    return safety_manager.report_incident(incident)

@router.get("/{competition_id}/safety/status", auth=safety_auth)
def get_safety_status(request, competition_id: int, location: Optional[str] = None) -> Dict:
    """Get current safety status for a location or the entire competition."""
    competition = get_object_or_404(Competition, id=competition_id)
    safety_manager = SafetyProtocolManager(competition_id)
    return safety_manager.get_safety_status(location)

@router.get("/{competition_id}/safety/requirements", auth=safety_auth)
def get_safety_requirements(request, competition_id: int, event_type: str) -> Dict:
    """Get safety requirements for a specific event type."""
    competition = get_object_or_404(Competition, id=competition_id)
    safety_manager = SafetyProtocolManager(competition_id)
    return safety_manager.get_safety_requirements(event_type)

@router.post("/{competition_id}/safety/validate", auth=safety_auth)
def validate_safety_setup(request, competition_id: int, query: SafetyRequirementQuery) -> Dict:
    """Validate that all safety requirements are met for an event."""
    competition = get_object_or_404(Competition, id=competition_id)
    safety_manager = SafetyProtocolManager(competition_id)
    return safety_manager.validate_safety_setup(
        event_type=query.event_type,
        location=query.location
    )

@router.get("/{competition_id}/safety/checklist/{check_type}", auth=safety_auth)
def get_safety_checklist(request, competition_id: int, check_type: str) -> Dict:
    """Get the checklist for a specific safety check type."""
    competition = get_object_or_404(Competition, id=competition_id)
    safety_manager = SafetyProtocolManager(competition_id)
    
    safety_check = safety_manager.safety_checks.get(check_type)
    if not safety_check:
        return {
            'status': 'error',
            'message': f'Unknown safety check type: {check_type}'
        }
    
    return {
        'check_type': check_type,
        'description': safety_check.description,
        'frequency': str(safety_check.frequency),
        'required_role': safety_check.required_role,
        'checklist': safety_check.checklist,
        'documentation_required': safety_check.documentation_required
    }

@router.get("/{competition_id}/safety/incidents", auth=safety_auth)
@require_competition_role(['Admin', 'Technical Delegate', 'Safety Officer'])
def list_safety_incidents(request, competition_id: int, 
                         status: Optional[str] = None,
                         severity: Optional[str] = None) -> List[Dict]:
    """List safety incidents with optional filtering."""
    competition = get_object_or_404(Competition, id=competition_id)
    
    # Get all incident keys from cache
    pattern = f"safety_incident_{competition_id}_*"
    incident_keys = [key for key in cache.keys(pattern)]
    
    # Get incidents from cache
    incidents = []
    for key in incident_keys:
        incident_data = cache.get(key)
        if incident_data:
            if status and incident_data['status'] != status:
                continue
            if severity and incident_data['severity'] != severity:
                continue
            incidents.append(incident_data)
    
    return sorted(incidents, key=lambda x: x['timestamp'], reverse=True)

@router.put("/{competition_id}/safety/incidents/{incident_id}/status", auth=safety_auth)
@require_competition_role(['Admin', 'Technical Delegate', 'Safety Officer'])
def update_incident_status(request, competition_id: int, incident_id: str,
                          status: str, resolution_notes: Optional[str] = None) -> Dict:
    """Update the status of a safety incident."""
    competition = get_object_or_404(Competition, id=competition_id)
    
    incident_data = cache.get(incident_id)
    if not incident_data:
        return {
            'status': 'error',
            'message': 'Incident not found'
        }
    
    incident_data['status'] = status
    incident_data['resolution_notes'] = resolution_notes
    incident_data['resolved_by'] = request.user.username
    incident_data['resolved_at'] = datetime.now().isoformat()
    
    # Update cache
    cache.set(incident_id, incident_data, timeout=86400)  # Cache for 24 hours
    
    return {
        'status': 'success',
        'message': 'Incident status updated successfully',
        'incident': incident_data
    }

@router.get("/{competition_id}/safety/summary", auth=safety_auth)
def get_safety_summary(request, competition_id: int) -> Dict:
    """Get a summary of all safety-related information."""
    competition = get_object_or_404(Competition, id=competition_id)
    safety_manager = SafetyProtocolManager(competition_id)
    
    # Get overall safety status
    status = safety_manager.get_safety_status()
    
    # Get recent incidents
    pattern = f"safety_incident_{competition_id}_*"
    incident_keys = [key for key in cache.keys(pattern)]
    recent_incidents = []
    for key in incident_keys:
        incident = cache.get(key)
        if incident and incident['timestamp'] > (datetime.now() - timedelta(days=1)):
            recent_incidents.append(incident)
    
    # Count incidents by status
    incident_counts = {}
    for incident in recent_incidents:
        incident_counts[incident['status']] = incident_counts.get(incident['status'], 0) + 1
    
    return {
        'overall_status': status['overall_status'],
        'last_updated': status['last_updated'],
        'pending_checks': [
            check_type for check_type, checks in status['checks'].items()
            if isinstance(checks, list) and any(c['status'] != SafetyStatus.PASSED.value for c in checks)
            or not isinstance(checks, list) and checks.get('status') != SafetyStatus.PASSED.value
        ],
        'recent_incidents': {
            'total': len(recent_incidents),
            'by_status': incident_counts
        },
        'active_warnings': [
            {
                'check_type': check_type,
                'location': check['location'],
                'status': check['status']
            }
            for check_type, checks in status['checks'].items()
            for check in (checks if isinstance(checks, list) else [checks])
            if check and check['status'] == SafetyStatus.NEEDS_INSPECTION.value
        ]
    } 