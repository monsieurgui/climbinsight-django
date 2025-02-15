from typing import List, Dict, Optional, Union
from datetime import datetime
from django.db import transaction
from django.core.cache import cache
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import Competition, CompetitionResult
from .scoring import (
    EnhancedScoringManager as ScoringManager, ClimbingDiscipline, Attempt,
    LeadAttempt, BoulderAttempt, SpeedAttempt
)
from leagues.ranking import RankingRule, FQMERules, IFSCRules

class ResultStatus:
    PENDING = "pending"
    VERIFIED = "verified"
    PUBLISHED = "published"
    APPEALED = "appealed"
    INVALIDATED = "invalidated"

class ResultManager:
    """Manages competition results."""
    
    def __init__(self, competition_id: int):
        self.competition_id = competition_id
        self.competition = Competition.objects.get(id=competition_id)
        self._scoring_managers = {}
        self.ruleset = self._get_competition_ruleset()
    
    def _get_competition_ruleset(self) -> RankingRule:
        """Get the ruleset for this competition based on its league."""
        if not self.competition.league_id:
            return IFSCRules()  # Default to IFSC rules for non-league competitions
            
        league_ruleset = self.competition.league.ruleset
        if league_ruleset.get('type') == 'FQME':
            return FQMERules()
        elif league_ruleset.get('type') == 'IFSC':
            return IFSCRules()
        return IFSCRules()  # Default to IFSC rules
    
    def _get_scoring_manager(self, discipline: ClimbingDiscipline) -> ScoringManager:
        """Get or create a scoring manager for a discipline."""
        if discipline not in self._scoring_managers:
            self._scoring_managers[discipline] = ScoringManager(
                discipline=discipline,
                ruleset=self.ruleset
            )
        return self._scoring_managers[discipline]
    
    @transaction.atomic
    def submit_attempt(self, athlete_id: int, category_id: int,
                      attempt_data: Dict, discipline: ClimbingDiscipline) -> Dict:
        """Submit and score a new attempt."""
        # Create appropriate attempt object based on discipline
        attempt_classes = {
            ClimbingDiscipline.LEAD: LeadAttempt,
            ClimbingDiscipline.BOULDER: BoulderAttempt,
            ClimbingDiscipline.SPEED: SpeedAttempt
        }
        
        attempt_class = attempt_classes.get(discipline)
        if not attempt_class:
            return {
                'status': 'error',
                'message': f'Unsupported discipline: {discipline}'
            }
        
        attempt = attempt_class(**attempt_data)
        
        # Get route data from competition
        route_data = self.competition.routes.get(
            category_id=category_id,
            discipline=discipline.value
        )
        
        # Add ruleset information to route data
        route_data['ruleset'] = {
            'type': self.ruleset.__class__.__name__,
            'points_table': self.ruleset.get_points_table(),
            'qualification_criteria': self.ruleset.get_qualification_criteria()
        }
        
        # Score the attempt
        scoring_manager = self._get_scoring_manager(discipline)
        score = scoring_manager.score_attempt(attempt, route_data)
        
        # Store the result
        result, created = CompetitionResult.objects.get_or_create(
            competition_id=self.competition_id,
            athlete_id=athlete_id,
            category_id=category_id,
            defaults={
                'score': score,
                'attempts': [attempt_data],
                'status': ResultStatus.PENDING,
                'ruleset_type': self.ruleset.__class__.__name__
            }
        )
        
        if not created:
            result.attempts.append(attempt_data)
            result.score = score
            result.save()
        
        # Invalidate relevant caches
        self._invalidate_result_caches(category_id)
        
        return {
            'status': 'success',
            'result_id': result.id,
            'score': score,
            'ruleset': self.ruleset.__class__.__name__
        }
    
    def get_results(self, category_id: Optional[int] = None,
                   status: Optional[str] = None) -> List[Dict]:
        """Get results, optionally filtered by category and status."""
        cache_key = f"results_{self.competition_id}_{category_id}_{status}"
        cached_results = cache.get(cache_key)
        
        if cached_results:
            return cached_results
        
        # Query results
        results = CompetitionResult.objects.filter(
            competition_id=self.competition_id
        )
        
        if category_id:
            results = results.filter(category_id=category_id)
        if status:
            results = results.filter(status=status)
        
        # Format results
        formatted_results = []
        for result in results:
            formatted_results.append({
                'athlete_id': result.athlete_id,
                'category_id': result.category_id,
                'score': result.score,
                'attempts': result.attempts,
                'status': result.status,
                'ranking': result.ranking
            })
        
        # Cache results for 5 minutes
        cache.set(cache_key, formatted_results, timeout=300)
        
        return formatted_results
    
    @transaction.atomic
    def verify_result(self, result_id: int, verifier_id: int,
                     verification_notes: Optional[str] = None) -> Dict:
        """Verify a competition result."""
        try:
            result = CompetitionResult.objects.get(
                id=result_id,
                competition_id=self.competition_id
            )
            
            if result.status != ResultStatus.PENDING:
                return {
                    'status': 'error',
                    'message': f'Result is not pending verification (current status: {result.status})'
                }
            
            result.status = ResultStatus.VERIFIED
            result.verification_data = {
                'verifier_id': verifier_id,
                'verified_at': datetime.now().isoformat(),
                'notes': verification_notes
            }
            result.save()
            
            self._invalidate_result_caches(result.category_id)
            
            return {
                'status': 'success',
                'message': 'Result verified successfully'
            }
            
        except CompetitionResult.DoesNotExist:
            return {
                'status': 'error',
                'message': 'Result not found'
            }
    
    @transaction.atomic
    def publish_results(self, category_id: Optional[int] = None) -> Dict:
        """Publish results for a category or all categories."""
        results = CompetitionResult.objects.filter(
            competition_id=self.competition_id,
            status=ResultStatus.VERIFIED
        )
        
        if category_id:
            results = results.filter(category_id=category_id)
        
        if not results.exists():
            return {
                'status': 'error',
                'message': 'No verified results found to publish'
            }
        
        # Update rankings before publishing
        self.update_rankings(category_id)
        
        # Publish results
        results.update(
            status=ResultStatus.PUBLISHED,
            published_at=datetime.now()
        )
        
        self._invalidate_result_caches(category_id)
        
        return {
            'status': 'success',
            'message': 'Results published successfully',
            'published_count': results.count()
        }
    
    @transaction.atomic
    def submit_appeal(self, result_id: int, athlete_id: int,
                     appeal_data: Dict) -> Dict:
        """Submit an appeal for a result."""
        try:
            result = CompetitionResult.objects.get(
                id=result_id,
                competition_id=self.competition_id,
                athlete_id=athlete_id
            )
            
            if result.status not in [ResultStatus.VERIFIED, ResultStatus.PUBLISHED]:
                return {
                    'status': 'error',
                    'message': f'Cannot appeal result with status: {result.status}'
                }
            
            result.status = ResultStatus.APPEALED
            result.appeal_data = {
                'submitted_at': datetime.now().isoformat(),
                'reason': appeal_data.get('reason'),
                'evidence': appeal_data.get('evidence'),
                'requested_score': appeal_data.get('requested_score'),
                'status': 'pending'
            }
            result.save()
            
            self._invalidate_result_caches(result.category_id)
            
            return {
                'status': 'success',
                'message': 'Appeal submitted successfully',
                'appeal_id': result.id
            }
            
        except CompetitionResult.DoesNotExist:
            return {
                'status': 'error',
                'message': 'Result not found'
            }
    
    @transaction.atomic
    def resolve_appeal(self, result_id: int, resolver_id: int,
                      resolution_data: Dict) -> Dict:
        """Resolve an appeal."""
        try:
            result = CompetitionResult.objects.get(
                id=result_id,
                competition_id=self.competition_id,
                status=ResultStatus.APPEALED
            )
            
            appeal_data = result.appeal_data
            appeal_data.update({
                'resolved_at': datetime.now().isoformat(),
                'resolver_id': resolver_id,
                'resolution': resolution_data.get('resolution'),
                'resolution_notes': resolution_data.get('notes'),
                'status': 'resolved'
            })
            
            if resolution_data.get('accepted', False):
                result.score = resolution_data.get('corrected_score', result.score)
                result.status = ResultStatus.VERIFIED
            else:
                result.status = resolution_data.get('revert_to_status', ResultStatus.VERIFIED)
            
            result.appeal_data = appeal_data
            result.save()
            
            # Update rankings if necessary
            if resolution_data.get('accepted', False):
                self.update_rankings(result.category_id)
            
            self._invalidate_result_caches(result.category_id)
            
            return {
                'status': 'success',
                'message': 'Appeal resolved successfully'
            }
            
        except CompetitionResult.DoesNotExist:
            return {
                'status': 'error',
                'message': 'Result not found'
            }
    
    def update_rankings(self, category_id: Optional[int] = None) -> None:
        """Update rankings for results in a category or all categories."""
        results = CompetitionResult.objects.filter(
            competition_id=self.competition_id
        )
        
        if category_id:
            results = results.filter(category_id=category_id)
        
        # Group results by category and discipline
        grouped_results = {}
        for result in results:
            key = (result.category_id, result.score.get('discipline'))
            if key not in grouped_results:
                grouped_results[key] = []
            grouped_results[key].append(result)
        
        # Update rankings for each group
        for (cat_id, discipline), group_results in grouped_results.items():
            scoring_manager = self._get_scoring_manager(ClimbingDiscipline(discipline))
            
            # Add ruleset-specific data for ranking calculation
            round_data = {
                'ruleset': self.ruleset.__class__.__name__,
                'points_table': self.ruleset.get_points_table(),
                'qualification_criteria': self.ruleset.get_qualification_criteria()
            }
            
            ranked_results = scoring_manager.calculate_rankings(
                [r.score for r in group_results],
                round_data
            )
            
            # Update rankings in database
            for rank, (result, ranked_data) in enumerate(zip(group_results, ranked_results), 1):
                result.ranking = rank
                result.save()
    
    def _invalidate_result_caches(self, category_id: Optional[int] = None) -> None:
        """Invalidate result caches."""
        patterns = [
            f"results_{self.competition_id}_*",
            f"rankings_{self.competition_id}_*"
        ]
        
        if category_id:
            patterns.extend([
                f"results_{self.competition_id}_{category_id}_*",
                f"rankings_{self.competition_id}_{category_id}_*"
            ])
        
        for pattern in patterns:
            cache_keys = cache.keys(pattern)
            if cache_keys:
                cache.delete_many(cache_keys) 