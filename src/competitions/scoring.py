from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import json
import os

from leagues.ranking import RankingRule, FQMERules, IFSCRules

def load_ruleset_config(ruleset_type: str) -> Dict:
    """Load ruleset configuration from JSON file."""
    config_path = os.path.join(
        os.path.dirname(__file__),
        '..',
        'leagues',
        'ranking_configs',
        f'{ruleset_type.lower()}.json'
    )
    with open(config_path, 'r') as f:
        return json.load(f)

class ClimbingDiscipline(Enum):
    LEAD = "lead"
    BOULDER = "boulder"
    SPEED = "speed"
    COMBINED = "combined"

class ScoringMethod(Enum):
    IFSC_LEAD = "ifsc_lead"
    IFSC_BOULDER = "ifsc_boulder"
    IFSC_SPEED = "ifsc_speed"
    FQME_LEAD = "fqme_lead"
    FQME_BOULDER = "fqme_boulder"
    CUSTOM = "custom"

@dataclass
class Attempt:
    """Represents a climbing attempt."""
    timestamp: datetime
    hold_reached: str  # Hold identifier
    is_top: bool
    time_taken: float  # In seconds
    is_valid: bool = True
    invalidation_reason: Optional[str] = None
    judge_id: Optional[int] = None
    video_url: Optional[str] = None

@dataclass
class BoulderAttempt(Attempt):
    """Boulder-specific attempt data."""
    zone_reached: bool = False
    num_tries_to_zone: int = 0
    num_tries_to_top: int = 0

@dataclass
class LeadAttempt(Attempt):
    """Lead climbing attempt data."""
    plus_modifier: bool = False  # For + holds
    clipping_points: List[str] = None  # List of quickdraws clipped
    fall_type: Optional[str] = None  # Type of fall if applicable

@dataclass
class SpeedAttempt(Attempt):
    """Speed climbing attempt data."""
    lane: str  # A or B
    false_start: bool = False
    reaction_time: Optional[float] = None  # In seconds
    split_times: List[float] = None  # List of split times

class ScoreCalculator:
    """Base class for score calculation."""
    
    def __init__(self, scoring_method: ScoringMethod, ruleset: Optional[RankingRule] = None):
        self.scoring_method = scoring_method
        self.ruleset = ruleset or self._get_default_ruleset()
        self.config = load_ruleset_config(self.ruleset.__class__.__name__)
    
    def _get_default_ruleset(self) -> RankingRule:
        """Get default ruleset based on scoring method."""
        if self.scoring_method.name.startswith('IFSC'):
            return IFSCRules()
        elif self.scoring_method.name.startswith('FQME'):
            return FQMERules()
        return IFSCRules()  # Default to IFSC rules
    
    def validate_attempt(self, attempt: Attempt) -> Dict:
        """Validate an attempt based on rules."""
        validation = {
            'is_valid': True,
            'issues': [],
            'warnings': []
        }
        
        # Basic validations
        if not attempt.hold_reached:
            validation['is_valid'] = False
            validation['issues'].append('No hold reached specified')
        
        if attempt.time_taken <= 0:
            validation['is_valid'] = False
            validation['issues'].append('Invalid time taken')
        
        if attempt.is_top and not attempt.hold_reached.endswith('TOP'):
            validation['warnings'].append('Top marked but hold is not marked as TOP')
        
        return validation

class LeadScoreCalculator(ScoreCalculator):
    """Calculator for lead climbing scores."""
    
    def calculate_score(self, attempt: LeadAttempt, route_data: Dict) -> Dict:
        """Calculate score for a lead climbing attempt."""
        if not self.validate_attempt(attempt)['is_valid']:
            return {'score': 0, 'valid': False}
        
        # Get hold values from route data
        holds = route_data.get('holds', {})
        hold_value = holds.get(attempt.hold_reached, 0)
        
        # Get scoring config
        scoring_config = self.config['scoring']['lead']
        
        # Add plus modifier if applicable
        if attempt.plus_modifier:
            hold_value += scoring_config['base_points']['plus_modifier_enhanced' if self.scoring_method.name.startswith('FQME') else 'plus_modifier']
        
        # Validate clipping points
        if route_data.get('required_clips'):
            missing_clips = set(route_data['required_clips']) - set(attempt.clipping_points or [])
            if missing_clips:
                return {
                    'score': hold_value,
                    'valid': False,
                    'issues': [f'Missing clips: {", ".join(missing_clips)}']
                }
        
        return {
            'score': hold_value,
            'valid': True,
            'hold_reached': attempt.hold_reached,
            'plus': attempt.plus_modifier,
            'time': attempt.time_taken,
            'ruleset': self.scoring_method.value
        }

class BoulderScoreCalculator(ScoreCalculator):
    """Calculator for boulder scores."""
    
    def calculate_score(self, attempt: BoulderAttempt, problem_data: Dict) -> Dict:
        """Calculate score for a boulder attempt."""
        if not self.validate_attempt(attempt)['is_valid']:
            return {'score': 0, 'valid': False}
        
        # Get scoring config
        scoring_config = self.config['scoring']['boulder']
        
        score = {
            'tops': 1 if attempt.is_top else 0,
            'zones': 1 if attempt.zone_reached else 0,
            'top_attempts': attempt.num_tries_to_top,
            'zone_attempts': attempt.num_tries_to_zone,
            'valid': True,
            'ruleset': self.scoring_method.value
        }
        
        # Calculate ranking score based on ruleset
        top_points = scoring_config['points']['top']
        zone_points = scoring_config['points']['zone']
        
        ranking_score = (top_points if attempt.is_top else 0) + (zone_points if attempt.zone_reached else 0)
        
        # Apply attempt penalties
        if attempt.is_top:
            penalty_config = scoring_config['penalties']['top_attempt']
            ranking_score -= min(
                attempt.num_tries_to_top * penalty_config['value'],
                penalty_config['max_deduction_10_attempts' if self.scoring_method.name.startswith('FQME') else 'max_deduction']
            )
            
        if attempt.zone_reached:
            penalty_config = scoring_config['penalties']['zone_attempt']
            ranking_score -= min(
                attempt.num_tries_to_zone * penalty_config['value'],
                penalty_config['max_deduction_10_attempts' if self.scoring_method.name.startswith('FQME') else 'max_deduction']
            )
        
        score['ranking_score'] = ranking_score
        return score

class SpeedScoreCalculator(ScoreCalculator):
    """Calculator for speed climbing scores."""
    
    def calculate_score(self, attempt: SpeedAttempt, route_data: Dict) -> Dict:
        """Calculate score for a speed attempt."""
        if not self.validate_attempt(attempt)['is_valid']:
            return {'score': 0, 'valid': False}
        
        # Get scoring config
        scoring_config = self.config['scoring']['speed']
        
        if attempt.false_start:
            return {
                'score': float('inf'),
                'valid': False,
                'reason': 'False start',
                'reaction_time': attempt.reaction_time
            }
        
        # Validate split times if required
        if route_data.get('split_points'):
            if not attempt.split_times or len(attempt.split_times) != len(route_data['split_points']):
                return {
                    'score': float('inf'),
                    'valid': False,
                    'reason': 'Missing or invalid split times'
                }
        
        return {
            'score': attempt.time_taken,
            'valid': True,
            'reaction_time': attempt.reaction_time,
            'split_times': attempt.split_times,
            'lane': attempt.lane,
            'follows_ifsc_rules': scoring_config.get('follows_ifsc_rules', True)
        }

class ScoringManager:
    """Manages scoring for competitions."""
    
    def __init__(self, discipline: ClimbingDiscipline, scoring_method: Optional[ScoringMethod] = None,
                 ruleset: Optional[RankingRule] = None):
        self.discipline = discipline
        self.scoring_method = scoring_method or self._get_default_scoring_method()
        self.ruleset = ruleset
        self.calculator = self._get_calculator()
    
    def _get_default_scoring_method(self) -> ScoringMethod:
        """Get default scoring method for discipline."""
        if self.ruleset:
            if isinstance(self.ruleset, FQMERules):
                defaults = {
                    ClimbingDiscipline.LEAD: ScoringMethod.FQME_LEAD,
                    ClimbingDiscipline.BOULDER: ScoringMethod.FQME_BOULDER,
                    ClimbingDiscipline.SPEED: ScoringMethod.IFSC_SPEED  # FQME uses IFSC speed rules
                }
            else:  # Default to IFSC
                defaults = {
                    ClimbingDiscipline.LEAD: ScoringMethod.IFSC_LEAD,
                    ClimbingDiscipline.BOULDER: ScoringMethod.IFSC_BOULDER,
                    ClimbingDiscipline.SPEED: ScoringMethod.IFSC_SPEED
                }
        else:
            defaults = {
                ClimbingDiscipline.LEAD: ScoringMethod.IFSC_LEAD,
                ClimbingDiscipline.BOULDER: ScoringMethod.IFSC_BOULDER,
                ClimbingDiscipline.SPEED: ScoringMethod.IFSC_SPEED
            }
        return defaults.get(self.discipline, ScoringMethod.CUSTOM)
    
    def _get_calculator(self) -> ScoreCalculator:
        """Get appropriate calculator based on discipline."""
        calculators = {
            ClimbingDiscipline.LEAD: LeadScoreCalculator,
            ClimbingDiscipline.BOULDER: BoulderScoreCalculator,
            ClimbingDiscipline.SPEED: SpeedScoreCalculator
        }
        calculator_class = calculators.get(self.discipline, ScoreCalculator)
        return calculator_class(self.scoring_method, self.ruleset)
    
    def score_attempt(self, attempt: Attempt, route_data: Dict) -> Dict:
        """Score an attempt using the appropriate calculator."""
        return self.calculator.calculate_score(attempt, route_data)
    
    def validate_attempt(self, attempt: Attempt) -> Dict:
        """Validate an attempt."""
        return self.calculator.validate_attempt(attempt)
    
    def calculate_rankings(self, attempts: List[Dict], round_data: Dict) -> List[Dict]:
        """Calculate rankings based on attempts."""
        if self.discipline == ClimbingDiscipline.LEAD:
            return self._calculate_lead_rankings(attempts)
        elif self.discipline == ClimbingDiscipline.BOULDER:
            return self._calculate_boulder_rankings(attempts)
        elif self.discipline == ClimbingDiscipline.SPEED:
            return self._calculate_speed_rankings(attempts)
        else:
            raise ValueError(f"Unsupported discipline: {self.discipline}")
    
    def _calculate_lead_rankings(self, attempts: List[Dict]) -> List[Dict]:
        """Calculate rankings for lead climbing."""
        # Sort by score (higher is better), then by time (lower is better)
        return sorted(
            attempts,
            key=lambda x: (-x['score'], x['time']),
            reverse=False
        )
    
    def _calculate_boulder_rankings(self, attempts: List[Dict]) -> List[Dict]:
        """Calculate rankings for bouldering."""
        # Sort by tops, then zones, then attempts
        return sorted(
            attempts,
            key=lambda x: (
                -x['tops'],
                -x['zones'],
                x['top_attempts'],
                x['zone_attempts']
            )
        )
    
    def _calculate_speed_rankings(self, attempts: List[Dict]) -> List[Dict]:
        """Calculate rankings for speed climbing."""
        # Sort by time (lower is better), false starts are last
        return sorted(
            attempts,
            key=lambda x: float('inf') if not x['valid'] else x['score']
        ) 