from typing import List, Dict, Optional
from ninja import Router, Schema
from django.shortcuts import get_object_or_404
from datetime import datetime

from .scoring import ClimbingDiscipline
from .results import ResultManager, ResultStatus
from .models import Competition
from .auth import CompetitionRoleAuth, require_competition_role
from leagues.ranking import RankingRule, FQMERules, IFSCRules

router = Router()
auth = CompetitionRoleAuth()

class AttemptSchema(Schema):
    timestamp: datetime
    hold_reached: str
    is_top: bool
    time_taken: float
    judge_id: Optional[int] = None
    video_url: Optional[str] = None

class LeadAttemptSchema(AttemptSchema):
    plus_modifier: bool = False
    clipping_points: Optional[List[str]] = None
    fall_type: Optional[str] = None

class BoulderAttemptSchema(AttemptSchema):
    zone_reached: bool = False
    num_tries_to_zone: int = 0
    num_tries_to_top: int = 0

class SpeedAttemptSchema(AttemptSchema):
    lane: str
    false_start: bool = False
    reaction_time: Optional[float] = None
    split_times: Optional[List[float]] = None

class AppealSchema(Schema):
    reason: str
    evidence: Optional[Dict] = None
    requested_score: Optional[Dict] = None

class AppealResolutionSchema(Schema):
    resolution: str
    notes: Optional[str] = None
    accepted: bool = False
    corrected_score: Optional[Dict] = None
    revert_to_status: Optional[str] = None

@router.get("/{competition_id}/ruleset", auth=auth)
def get_ruleset_info(request, competition_id: int) -> Dict:
    """Get information about the competition's scoring ruleset."""
    competition = get_object_or_404(Competition, id=competition_id)
    result_manager = ResultManager(competition_id)
    
    ruleset = result_manager.ruleset
    return {
        'type': ruleset.__class__.__name__,
        'description': ruleset.get_rule_info()['description'],
        'features': ruleset.get_rule_info()['features'],
        'points_table': ruleset.get_points_table(),
        'qualification_criteria': ruleset.get_qualification_criteria()
    }

@router.post("/{competition_id}/attempts", auth=auth)
@require_competition_role(['Judge', 'Admin'])
def submit_attempt(request, competition_id: int, athlete_id: int,
                  category_id: int, discipline: str, attempt: Dict) -> Dict:
    """Submit a new attempt for scoring."""
    competition = get_object_or_404(Competition, id=competition_id)
    result_manager = ResultManager(competition_id)
    
    # Convert discipline string to enum
    try:
        discipline_enum = ClimbingDiscipline(discipline.lower())
    except ValueError:
        return {
            'status': 'error',
            'message': f'Invalid discipline: {discipline}'
        }
    
    # Validate and submit attempt
    result = result_manager.submit_attempt(
        athlete_id=athlete_id,
        category_id=category_id,
        attempt_data=attempt,
        discipline=discipline_enum
    )
    
    # Add ruleset information to response
    if result['status'] == 'success':
        result['ruleset_info'] = {
            'type': result_manager.ruleset.__class__.__name__,
            'points_table': result_manager.ruleset.get_points_table()
        }
    
    return result

@router.get("/{competition_id}/results", auth=auth)
def get_results(request, competition_id: int,
                category_id: Optional[int] = None,
                status: Optional[str] = None) -> List[Dict]:
    """Get competition results."""
    competition = get_object_or_404(Competition, id=competition_id)
    result_manager = ResultManager(competition_id)
    
    results = result_manager.get_results(category_id, status)
    
    # Add ruleset information
    ruleset_info = {
        'type': result_manager.ruleset.__class__.__name__,
        'description': result_manager.ruleset.get_rule_info()['description']
    }
    
    return {
        'ruleset': ruleset_info,
        'results': results
    }

@router.post("/{competition_id}/results/{result_id}/verify", auth=auth)
@require_competition_role(['Judge', 'Admin', 'Technical Delegate'])
def verify_result(request, competition_id: int, result_id: int,
                 verification_notes: Optional[str] = None) -> Dict:
    """Verify a competition result."""
    competition = get_object_or_404(Competition, id=competition_id)
    result_manager = ResultManager(competition_id)
    return result_manager.verify_result(
        result_id=result_id,
        verifier_id=request.user.id,
        verification_notes=verification_notes
    )

@router.post("/{competition_id}/results/publish", auth=auth)
@require_competition_role(['Admin', 'Technical Delegate'])
def publish_results(request, competition_id: int,
                   category_id: Optional[int] = None) -> Dict:
    """Publish results for a category or all categories."""
    competition = get_object_or_404(Competition, id=competition_id)
    result_manager = ResultManager(competition_id)
    return result_manager.publish_results(category_id)

@router.post("/{competition_id}/results/{result_id}/appeal", auth=auth)
def submit_appeal(request, competition_id: int, result_id: int,
                 appeal: AppealSchema) -> Dict:
    """Submit an appeal for a result."""
    competition = get_object_or_404(Competition, id=competition_id)
    result_manager = ResultManager(competition_id)
    return result_manager.submit_appeal(
        result_id=result_id,
        athlete_id=request.user.id,
        appeal_data=appeal.dict()
    )

@router.post("/{competition_id}/results/{result_id}/resolve-appeal", auth=auth)
@require_competition_role(['Admin', 'Technical Delegate', 'Jury President'])
def resolve_appeal(request, competition_id: int, result_id: int,
                  resolution: AppealResolutionSchema) -> Dict:
    """Resolve an appeal."""
    competition = get_object_or_404(Competition, id=competition_id)
    result_manager = ResultManager(competition_id)
    return result_manager.resolve_appeal(
        result_id=result_id,
        resolver_id=request.user.id,
        resolution_data=resolution.dict()
    )

@router.get("/{competition_id}/results/status", auth=auth)
def get_result_status(request, competition_id: int,
                     category_id: Optional[int] = None) -> Dict:
    """Get status summary of results."""
    competition = get_object_or_404(Competition, id=competition_id)
    result_manager = ResultManager(competition_id)
    
    results = result_manager.get_results(category_id)
    
    status_counts = {
        ResultStatus.PENDING: 0,
        ResultStatus.VERIFIED: 0,
        ResultStatus.PUBLISHED: 0,
        ResultStatus.APPEALED: 0,
        ResultStatus.INVALIDATED: 0
    }
    
    for result in results:
        status_counts[result['status']] = status_counts.get(result['status'], 0) + 1
    
    return {
        'total_results': len(results),
        'status_counts': status_counts,
        'can_publish': status_counts[ResultStatus.VERIFIED] > 0,
        'has_pending_appeals': status_counts[ResultStatus.APPEALED] > 0
    }

@router.get("/{competition_id}/results/{result_id}/history", auth=auth)
def get_result_history(request, competition_id: int, result_id: int) -> List[Dict]:
    """Get history of a result including verifications and appeals."""
    competition = get_object_or_404(Competition, id=competition_id)
    result = get_object_or_404(CompetitionResult, id=result_id, competition_id=competition_id)
    
    history = []
    
    # Add initial submission
    history.append({
        'type': 'submission',
        'timestamp': result.created_at.isoformat(),
        'data': {
            'score': result.score,
            'attempts': result.attempts
        }
    })
    
    # Add verification if exists
    if hasattr(result, 'verification_data'):
        history.append({
            'type': 'verification',
            'timestamp': result.verification_data.get('verified_at'),
            'data': result.verification_data
        })
    
    # Add appeal if exists
    if hasattr(result, 'appeal_data'):
        history.append({
            'type': 'appeal',
            'timestamp': result.appeal_data.get('submitted_at'),
            'data': {
                'reason': result.appeal_data.get('reason'),
                'status': result.appeal_data.get('status')
            }
        })
        
        # Add appeal resolution if exists
        if result.appeal_data.get('resolved_at'):
            history.append({
                'type': 'appeal_resolution',
                'timestamp': result.appeal_data.get('resolved_at'),
                'data': {
                    'resolution': result.appeal_data.get('resolution'),
                    'accepted': result.appeal_data.get('accepted', False)
                }
            })
    
    return sorted(history, key=lambda x: x['timestamp']) 