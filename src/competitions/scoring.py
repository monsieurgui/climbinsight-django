from typing import List, Dict, Optional, Union
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import json
import os

from leagues.ranking import RankingRule, FQMERules, IFSCRules
from leagues.rulesets import CustomRuleSet, DynamicPointSystem
from leagues.validators import RulesetValidator

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
    timestamp: datetime
    hold_reached: str
    is_top: bool
    time_taken: float
    is_valid: bool = True                    # has default
    invalidation_reason: Optional[str] = None # has default
    judge_id: Optional[int] = None           # has default
    video_url: Optional[str] = None          # has default

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
    lane: str = None  # A or B
    false_start: bool = False
    reaction_time: Optional[float] = None  # In seconds
    split_times: Optional[List[float]] = None  # List of split times

    def __post_init__(self):
        if self.lane is None:
            raise ValueError("lane is required for SpeedAttempt")

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

class EnhancedScoringManager:
    """Enhanced scoring manager with support for custom rulesets and dynamic scoring."""
    
    def __init__(self, 
                 discipline: ClimbingDiscipline,
                 scoring_method: Optional[ScoringMethod] = None,
                 ruleset: Optional[Union[RankingRule, CustomRuleSet]] = None,
                 custom_config: Optional[Dict] = None):
        self.discipline = discipline
        self.scoring_method = scoring_method or self._get_default_scoring_method()
        
        # Initialize ruleset
        if ruleset:
            self.ruleset = ruleset
        elif custom_config:
            self.ruleset = CustomRuleSet(config_dict=custom_config)
        else:
            self.ruleset = self._get_default_ruleset()
            
        # Initialize point system
        if isinstance(self.ruleset, CustomRuleSet):
            self.point_system = self.ruleset.point_system
        else:
            self.point_system = DynamicPointSystem(load_ruleset_config(
                self.ruleset.__class__.__name__.replace('Rules', '')
            ))
            
        # Initialize appropriate calculator based on discipline
        self.calculator = self._get_calculator()
    
    def _get_default_scoring_method(self) -> ScoringMethod:
        """Get default scoring method for discipline."""
        if isinstance(self.ruleset, FQMERules):
            defaults = {
                ClimbingDiscipline.LEAD: ScoringMethod.FQME_LEAD,
                ClimbingDiscipline.BOULDER: ScoringMethod.FQME_BOULDER,
                ClimbingDiscipline.SPEED: ScoringMethod.IFSC_SPEED
            }
        else:
            defaults = {
                ClimbingDiscipline.LEAD: ScoringMethod.IFSC_LEAD,
                ClimbingDiscipline.BOULDER: ScoringMethod.IFSC_BOULDER,
                ClimbingDiscipline.SPEED: ScoringMethod.IFSC_SPEED
            }
        return defaults.get(self.discipline, ScoringMethod.IFSC_LEAD)
    
    def _get_calculator(self):
        """Get appropriate calculator based on discipline."""
        calculators = {
            ClimbingDiscipline.LEAD: LeadScoreCalculator,
            ClimbingDiscipline.BOULDER: BoulderScoreCalculator,
            ClimbingDiscipline.SPEED: SpeedScoreCalculator
        }
        calculator_class = calculators.get(self.discipline)
        if not calculator_class:
            raise ValueError(f"Unsupported discipline: {self.discipline}")
        return calculator_class(self.scoring_method, self.ruleset)
    
    def calculate_rankings(self, attempts: List[Dict], round_data: Dict) -> Dict:
        """Calculate rankings with enhanced features."""
        # Calculate base rankings
        rankings = self.calculator.calculate_rankings(attempts, round_data)
        
        # Add statistical analysis
        stats = self._calculate_statistics(rankings)
        
        # Add performance metrics
        metrics = self._calculate_performance_metrics(rankings)
        
        # Add countback information if needed
        countback = None
        if self.ruleset.config.get('ranking', {}).get('tiebreak', {}).get('methods', []):
            if 'countback' in self.ruleset.config['ranking']['tiebreak']['methods']:
                countback = self._calculate_countback(rankings)
        
        return {
            'rankings': rankings,
            'statistics': stats,
            'performance_metrics': metrics,
            'countback': countback
        }
    
    def _calculate_statistics(self, rankings: List[Dict]) -> Dict:
        """Calculate statistical information about the rankings."""
        if not rankings:
            return {}
            
        scores = [r['score'] for r in rankings]
        return {
            'average_score': sum(scores) / len(scores),
            'max_score': max(scores),
            'min_score': min(scores),
            'score_distribution': self._calculate_distribution(scores),
            'participant_count': len(rankings),
            'completion_rate': len([r for r in rankings if r.get('completed', False)]) / len(rankings)
        }
    
    def _calculate_performance_metrics(self, rankings: List[Dict]) -> Dict:
        """Calculate advanced performance metrics."""
        metrics = {}
        
        for ranking in rankings:
            athlete_id = ranking['athlete_id']
            metrics[athlete_id] = {
                'consistency': self._calculate_consistency(ranking),
                'efficiency': self._calculate_efficiency(ranking),
                'technical_score': self._calculate_technical_score(ranking),
                'comparative_performance': self._calculate_comparative_performance(ranking, rankings)
            }
        
        return metrics
    
    def _calculate_distribution(self, values: List[float]) -> Dict:
        """Calculate distribution of values in ranges."""
        if not values:
            return {}
            
        min_val = min(values)
        max_val = max(values)
        range_size = (max_val - min_val) / 10  # 10 ranges
        
        distribution = {}
        for i in range(10):
            range_start = min_val + (i * range_size)
            range_end = range_start + range_size
            range_key = f"{range_start:.1f}-{range_end:.1f}"
            distribution[range_key] = len([v for v in values if range_start <= v < range_end])
            
        return distribution
    
    def _calculate_consistency(self, ranking: Dict) -> float:
        """Calculate athlete's consistency score."""
        attempts = ranking.get('attempts', [])
        if not attempts:
            return 0.0
            
        # Calculate variation in performance
        scores = [a.get('score', 0) for a in attempts]
        if not scores:
            return 0.0
            
        mean_score = sum(scores) / len(scores)
        variations = [(s - mean_score) ** 2 for s in scores]
        variance = sum(variations) / len(variations)
        
        # Convert to consistency score (0-1)
        max_variance = mean_score ** 2  # Theoretical maximum variance
        consistency = 1 - (variance / max_variance if max_variance > 0 else 0)
        
        return round(consistency, 2)
    
    def _calculate_efficiency(self, ranking: Dict) -> float:
        """Calculate athlete's efficiency score."""
        attempts = ranking.get('attempts', [])
        if not attempts:
            return 0.0
            
        successful_attempts = len([a for a in attempts if a.get('is_valid', False)])
        return round(successful_attempts / len(attempts), 2)
    
    def _calculate_technical_score(self, ranking: Dict) -> float:
        """Calculate athlete's technical score."""
        attempts = ranking.get('attempts', [])
        if not attempts:
            return 0.0
            
        # Factors to consider for technical score
        factors = {
            'hold_efficiency': self._calculate_hold_efficiency(attempts),
            'time_efficiency': self._calculate_time_efficiency(attempts),
            'movement_quality': self._calculate_movement_quality(attempts)
        }
        
        # Weighted average of factors
        weights = {'hold_efficiency': 0.4, 'time_efficiency': 0.3, 'movement_quality': 0.3}
        technical_score = sum(score * weights[factor] for factor, score in factors.items())
        
        return round(technical_score, 2)
    
    def _calculate_comparative_performance(self, ranking: Dict, all_rankings: List[Dict]) -> float:
        """Calculate athlete's performance compared to the field."""
        if not all_rankings:
            return 0.0
            
        athlete_score = ranking.get('score', 0)
        all_scores = [r.get('score', 0) for r in all_rankings]
        
        if not all_scores:
            return 0.0
            
        average_score = sum(all_scores) / len(all_scores)
        if average_score == 0:
            return 0.0
            
        relative_performance = (athlete_score - average_score) / average_score
        
        return round(relative_performance, 2)
    
    def _calculate_hold_efficiency(self, attempts: List[Dict]) -> float:
        """Calculate efficiency in using holds."""
        if not attempts:
            return 0.0
            
        hold_scores = []
        for attempt in attempts:
            holds_used = attempt.get('holds_used', [])
            if holds_used:
                score = attempt.get('score', 0)
                hold_score = score / len(holds_used) if holds_used else 0
                hold_scores.append(hold_score)
                
        return sum(hold_scores) / len(hold_scores) if hold_scores else 0.0
    
    def _calculate_time_efficiency(self, attempts: List[Dict]) -> float:
        """Calculate time efficiency."""
        if not attempts:
            return 0.0
            
        time_scores = []
        for attempt in attempts:
            time_taken = attempt.get('time_taken', 0)
            if time_taken > 0:
                score = attempt.get('score', 0)
                time_score = score / time_taken
                time_scores.append(time_score)
                
        return sum(time_scores) / len(time_scores) if time_scores else 0.0
    
    def _calculate_movement_quality(self, attempts: List[Dict]) -> float:
        """Calculate movement quality score."""
        if not attempts:
            return 0.0
            
        quality_scores = []
        for attempt in attempts:
            # Factors affecting movement quality
            factors = {
                'fluidity': attempt.get('movement_fluidity', 0),
                'balance': attempt.get('balance_control', 0),
                'technique': attempt.get('technique_score', 0)
            }
            
            if any(factors.values()):
                quality_score = sum(factors.values()) / len(factors)
                quality_scores.append(quality_score)
                
        return sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
    
    def _calculate_countback(self, rankings: List[Dict]) -> Dict:
        """Calculate countback information for rankings."""
        countback = {}
        
        for ranking in rankings:
            athlete_id = ranking['athlete_id']
            attempts = ranking.get('attempts', [])
            
            # Count placements
            placements = {}
            for attempt in attempts:
                place = attempt.get('placement', 0)
                if place > 0:
                    placements[place] = placements.get(place, 0) + 1
                    
            countback[athlete_id] = {
                'placements': placements,
                'best_place': min(placements.keys()) if placements else None,
                'placement_counts': dict(sorted(placements.items()))
            }
            
        return countback 