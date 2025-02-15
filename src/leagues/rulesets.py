from typing import List, Dict, Optional, Union
from dataclasses import dataclass
from datetime import date
import json
import os
from pathlib import Path

from .validators import RulesetValidator, ValidationResult

class DynamicPointSystem:
    """Handles dynamic point calculations based on competition parameters."""
    
    def __init__(self, base_config: Dict):
        self.base_config = base_config
        self.scoring_config = base_config.get('scoring', {})
        
    def calculate_points(self, 
                        placement: int, 
                        competition_level: str,
                        discipline: str,
                        participant_count: int,
                        competition_importance: float = 1.0,
                        additional_factors: Optional[Dict] = None) -> int:
        """
        Calculate points with dynamic adjustments.
        
        Args:
            placement: Final placement in the competition
            competition_level: Level of competition (e.g., 'provincial', 'world_cup')
            discipline: Climbing discipline ('lead', 'boulder', 'speed')
            participant_count: Number of participants
            competition_importance: Importance multiplier (default: 1.0)
            additional_factors: Additional factors to consider in calculation
        
        Returns:
            Calculated points as integer
        """
        # Get base points from config
        discipline_config = self.scoring_config.get(discipline, {})
        ranking_points = discipline_config.get('ranking_points', {})
        
        # Get points table for the competition level
        points_table = ranking_points.get(competition_level, {})
        if isinstance(points_table, dict) and 'multiplier' in points_table:
            # If it's using a multiplier, get the base points and apply multiplier
            base_level = next((k for k in ranking_points.keys() if isinstance(ranking_points[k], dict) and 'multiplier' not in ranking_points[k]), None)
            if base_level:
                base_points = ranking_points[base_level].get(str(placement), 0)
                points = base_points * points_table['multiplier']
            else:
                points = 0
        else:
            # Direct points from table
            points = points_table.get(str(placement), 0)
        
        # Apply competition importance multiplier
        points *= competition_importance
        
        # Apply participant count adjustments
        participant_factor = self._calculate_participant_factor(participant_count)
        points *= participant_factor
        
        # Apply additional factors if provided
        if additional_factors:
            points *= self._apply_additional_factors(additional_factors)
        
        return int(round(points))
    
    def _calculate_participant_factor(self, participant_count: int) -> float:
        """Calculate adjustment factor based on participant count."""
        if participant_count <= 10:
            return 0.8  # Reduced points for very small competitions
        elif participant_count <= 20:
            return 0.9
        elif participant_count >= 100:
            return 1.1  # Bonus for large competitions
        elif participant_count >= 50:
            return 1.05
        return 1.0
    
    def _apply_additional_factors(self, factors: Dict) -> float:
        """Apply additional competition-specific factors."""
        multiplier = 1.0
        
        # Season finale bonus
        if factors.get('is_season_finale'):
            multiplier *= 1.2
            
        # Weather conditions (for outdoor competitions)
        if 'weather_condition' in factors:
            weather_multipliers = {
                'extreme_heat': 1.1,
                'rain': 1.15,
                'snow': 1.2,
                'optimal': 1.0
            }
            multiplier *= weather_multipliers.get(factors['weather_condition'], 1.0)
            
        # Competition history
        if factors.get('historical_importance'):
            multiplier *= 1.1
            
        return multiplier

class CustomRuleSet:
    """Support for custom competition rulesets."""
    
    def __init__(self, config_path: str = None, config_dict: Dict = None):
        """
        Initialize custom ruleset from either a file path or a dictionary.
        
        Args:
            config_path: Path to JSON configuration file
            config_dict: Dictionary containing configuration
        """
        if config_path and config_dict:
            raise ValueError("Provide either config_path or config_dict, not both")
            
        if config_path:
            self.config = self._load_custom_config(config_path)
        elif config_dict:
            self.config = config_dict
        else:
            raise ValueError("Must provide either config_path or config_dict")
            
        # Validate configuration
        self._validate_config()
        
        # Initialize point system
        self.point_system = DynamicPointSystem(self.config)
    
    def _load_custom_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file."""
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config
    
    def _validate_config(self) -> None:
        """Validate the configuration using RulesetValidator."""
        validator = RulesetValidator()
        result = validator.validate_ruleset(self.config)
        
        if not result.is_valid:
            raise ValueError(f"Invalid ruleset configuration:\n" + "\n".join(result.errors))
            
        if result.warnings:
            print("Ruleset configuration warnings:\n" + "\n".join(result.warnings))
    
    def get_points(self, 
                  placement: int,
                  competition_data: Dict) -> int:
        """
        Calculate points for a given placement using the custom ruleset.
        
        Args:
            placement: Final placement in the competition
            competition_data: Dictionary containing competition details
                - level: Competition level
                - discipline: Climbing discipline
                - participant_count: Number of participants
                - importance: Competition importance factor
                - additional_factors: Any additional factors to consider
        """
        return self.point_system.calculate_points(
            placement=placement,
            competition_level=competition_data['level'],
            discipline=competition_data['discipline'],
            participant_count=competition_data['participant_count'],
            competition_importance=competition_data.get('importance', 1.0),
            additional_factors=competition_data.get('additional_factors')
        )
    
    def get_qualification_criteria(self, category: Optional[str] = None) -> Dict:
        """Get qualification criteria, optionally for a specific category."""
        criteria = self.config['qualification_criteria']
        
        if category and 'category_requirements' in criteria:
            return criteria['category_requirements'].get(category, criteria)
        return criteria
    
    def check_qualification(self, 
                          results: List[Dict],
                          category: Optional[str] = None) -> Dict:
        """
        Check if results meet qualification criteria.
        
        Args:
            results: List of competition results
            category: Optional category to check specific requirements
            
        Returns:
            Dictionary containing qualification status and details
        """
        criteria = self.get_qualification_criteria(category)
        
        # Basic checks
        min_competitions = criteria['min_competitions']
        min_points = criteria['min_points']
        
        total_competitions = len(results)
        total_points = sum(r['points'] for r in results)
        
        # Check competition levels if required
        level_requirements = {}
        for key, value in criteria.items():
            if key.startswith('min_') and key not in ['min_competitions', 'min_points']:
                level = key.replace('min_', '')
                level_requirements[level] = value
        
        level_counts = {}
        for level in level_requirements:
            level_counts[level] = len([r for r in results if r['competition_level'] == level])
        
        # Determine qualification status
        qualified = (
            total_competitions >= min_competitions and
            total_points >= min_points and
            all(level_counts.get(level, 0) >= count 
                for level, count in level_requirements.items())
        )
        
        return {
            'qualified': qualified,
            'total_competitions': total_competitions,
            'total_points': total_points,
            'level_counts': level_counts,
            'missing_requirements': {
                'competitions': max(0, min_competitions - total_competitions),
                'points': max(0, min_points - total_points),
                'levels': {
                    level: max(0, count - level_counts.get(level, 0))
                    for level, count in level_requirements.items()
                }
            }
        }
    
    def handle_derogation(self, 
                         rankings: List[Dict],
                         derogation_athletes: List[int]) -> List[Dict]:
        """
        Handle rankings for athletes under derogation.
        
        Args:
            rankings: List of current rankings
            derogation_athletes: List of athlete IDs under derogation
            
        Returns:
            Updated rankings list
        """
        if not self.config.get('derogation', {}).get('enabled', False):
            return rankings
            
        derogation_rules = self.config['derogation']['rules']
        handling_method = derogation_rules['points_handling']
        
        for ranking in rankings:
            if ranking['athlete_id'] in derogation_athletes:
                original_points = ranking['points']
                original_ranking = ranking['ranking']
                
                if handling_method == 'redistribute':
                    # Find next athlete to receive points
                    next_athlete = next(
                        (r for r in rankings 
                         if r['ranking'] > ranking['ranking'] 
                         and r['athlete_id'] not in derogation_athletes),
                        None
                    )
                    if next_athlete:
                        ranking['points_source_athlete'] = next_athlete['athlete_id']
                        
                elif handling_method == 'zero':
                    ranking['points'] = 0
                    
                # Store original values
                ranking['under_derogation'] = True
                ranking['original_points'] = original_points
                ranking['original_ranking'] = original_ranking
                ranking['derogation_note'] = derogation_rules['display_note']
        
        return rankings 