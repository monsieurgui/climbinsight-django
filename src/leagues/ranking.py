from typing import List, Dict, Optional, Protocol, Type, Tuple
from decimal import Decimal
from dataclasses import dataclass
from datetime import date
from abc import ABC, abstractmethod
import importlib
import json
from pathlib import Path
from enum import Enum
import os

class RuleSet(Enum):
    """Available rule sets for league configuration."""
    FQME = "FQME"
    IFSC = "IFSC"

@dataclass
class CompetitionResult:
    placement: int
    points: int
    competition_level: str
    date: date
    category: str
    athlete_id: int
    countback_results: Optional[Dict] = None  # For IFSC countback system

class RankingRule(ABC):
    """Abstract base class for ranking rules."""
    
    def __init__(self, **kwargs):
        self.config = load_ruleset_config(self.__class__.__name__.replace('Rules', ''))
        self.kwargs = kwargs
    
    @abstractmethod
    def get_points_table(self) -> Dict[str, Dict[int, int]]:
        """Return the points table for different competition levels."""
        pass
    
    @abstractmethod
    def get_best_n_results(self) -> int:
        """Return the number of best results to consider."""
        pass
    
    @abstractmethod
    def get_qualification_criteria(self) -> Dict:
        """Return the qualification criteria."""
        pass
    
    @abstractmethod
    def handle_ties(self, rankings: List[Dict]) -> List[Dict]:
        """Handle ties in rankings according to specific rules."""
        pass
    
    @classmethod
    def get_rule_info(cls) -> Dict:
        """Return information about the rule set for UI display."""
        config = load_ruleset_config(cls.__name__.replace('Rules', ''))
        return {
            'name': config['name'],
            'description': config['description'],
            'features': config['features']
        }

class FQMERules(RankingRule):
    """FQME-specific ranking rules."""
    
    def get_points_table(self) -> Dict[str, Dict[int, int]]:
        points_table = {}
        scoring_config = self.config['scoring']
        
        # Get provincial points directly
        provincial = scoring_config['lead']['ranking_points']['provincial']
        points_table['provincial'] = {int(k): v for k, v in provincial.items()}
        
        # Calculate regional points (70% of provincial)
        regional_multiplier = scoring_config['lead']['ranking_points']['regional']['multiplier']
        points_table['regional'] = {k: int(v * regional_multiplier) for k, v in points_table['provincial'].items()}
        
        # Calculate local points (50% of provincial)
        local_multiplier = scoring_config['lead']['ranking_points']['local']['multiplier']
        points_table['local'] = {k: int(v * local_multiplier) for k, v in points_table['provincial'].items()}
        
        return points_table
    
    def get_best_n_results(self) -> int:
        return self.config['ranking']['best_n_results']
    
    def get_qualification_criteria(self) -> Dict:
        return self.config['qualification_criteria']
    
    def handle_ties(self, rankings: List[Dict]) -> List[Dict]:
        """
        FQME tie-breaking system:
        1. Compare head-to-head performance
        2. Compare most recent competition results
        3. Compare number of provincial competitions
        """
        # Sort by points first
        rankings.sort(key=lambda x: x['points'], reverse=True)
        
        current_rank = 1
        i = 0
        while i < len(rankings):
            # Find all athletes tied at current points
            tied_start = i
            current_points = rankings[i]['points']
            while (i + 1 < len(rankings) and 
                   rankings[i + 1]['points'] == current_points):
                i += 1
            tied_end = i + 1
            
            if tied_end - tied_start > 1:
                # Handle tie using methods from config
                tied_athletes = rankings[tied_start:tied_end]
                tiebreak_methods = self.config['ranking']['tiebreak']['methods']
                
                for method in tiebreak_methods:
                    if method == 'head_to_head':
                        # Compare head-to-head results
                        pass  # Implementation depends on available data
                    elif method == 'most_recent':
                        tied_athletes.sort(
                            key=lambda x: x.get('last_competition_date', date.min),
                            reverse=True
                        )
                    elif method == 'most_provincial':
                        tied_athletes.sort(
                            key=lambda x: x.get('competitions_count', {}).get('provincial', 0),
                            reverse=True
                        )
                
                # Update rankings with resolved ties
                for j, athlete in enumerate(tied_athletes, start=tied_start):
                    rankings[j] = athlete
                    rankings[j]['rank'] = current_rank
                    rankings[j]['tied_with'] = [
                        a['athlete_id'] for a in tied_athletes
                        if a['points'] == athlete['points'] and 
                        a['athlete_id'] != athlete['athlete_id']
                    ]
            
            i += 1
            current_rank = i + 1
        
        return rankings

class IFSCRules(RankingRule):
    """IFSC (International Federation of Sport Climbing) rules."""
    
    def get_points_table(self) -> Dict[str, Dict[int, int]]:
        points_table = {}
        scoring_config = self.config['scoring']
        
        # Get World Cup points directly
        world_cup = scoring_config['lead']['ranking_points']['world_cup']
        points_table['world_cup'] = {int(k): v for k, v in world_cup.items()}
        
        # Calculate World Championship points (150% of World Cup)
        wc_multiplier = scoring_config['lead']['ranking_points']['world_championship']['multiplier']
        points_table['world_championship'] = {k: int(v * wc_multiplier) for k, v in points_table['world_cup'].items()}
        
        # Calculate Continental points (80% of World Cup)
        cont_multiplier = scoring_config['lead']['ranking_points']['continental']['multiplier']
        points_table['continental'] = {k: int(v * cont_multiplier) for k, v in points_table['world_cup'].items()}
        
        return points_table
    
    def get_best_n_results(self) -> int:
        return self.config['ranking']['best_n_results']
    
    def get_qualification_criteria(self) -> Dict:
        return self.config['qualification_criteria']
    
    def handle_ties(self, rankings: List[Dict]) -> List[Dict]:
        """
        IFSC tie-breaking system from config:
        1. Compare number of better places (countback)
        2. Compare head-to-head performance
        3. Compare most recent competition results
        """
        # Sort by points first
        rankings.sort(key=lambda x: x['points'], reverse=True)
        
        current_rank = 1
        i = 0
        while i < len(rankings):
            # Find all athletes tied at current points
            tied_start = i
            current_points = rankings[i]['points']
            while (i + 1 < len(rankings) and 
                   rankings[i + 1]['points'] == current_points):
                i += 1
            tied_end = i + 1
            
            if tied_end - tied_start > 1:
                # Handle tie using methods from config
                tied_athletes = rankings[tied_start:tied_end]
                tiebreak_methods = self.config['ranking']['tiebreak']['methods']
                
                for method in tiebreak_methods:
                    if method == 'countback':
                        tied_athletes.sort(
                            key=lambda x: (
                                [-x.get('countback_results', {}).get(place, 0) 
                                 for place in range(1, 31)]
                            ),
                            reverse=True
                        )
                    elif method == 'head_to_head':
                        # Compare head-to-head results
                        pass  # Implementation depends on available data
                    elif method == 'most_recent':
                        tied_athletes.sort(
                            key=lambda x: x.get('last_competition_date', date.min),
                            reverse=True
                        )
                
                # Update rankings with resolved ties
                for j, athlete in enumerate(tied_athletes, start=tied_start):
                    rankings[j] = athlete
                    rankings[j]['rank'] = current_rank
                    rankings[j]['tied_with'] = [
                        a['athlete_id'] for a in tied_athletes
                        if a['points'] == athlete['points'] and 
                        a['athlete_id'] != athlete['athlete_id']
                    ]
            
            i += 1
            current_rank = i + 1
        
        return rankings

class RankingCalculator:
    """
    Dynamic ranking calculator that supports different rule sets.
    """
    
    AVAILABLE_RULES = {
        RuleSet.FQME: FQMERules,
        RuleSet.IFSC: IFSCRules
    }
    
    def __init__(self, rules: RankingRule):
        self.rules = rules
        self.points_table = rules.get_points_table()
        self.best_n_results = rules.get_best_n_results()
    
    @classmethod
    def get_available_rules(cls) -> List[Dict]:
        """Return list of available rule sets for UI selection."""
        return [rule_class.get_rule_info() 
                for rule_class in cls.AVAILABLE_RULES.values()]
    
    @classmethod
    def create_from_ruleset(cls, ruleset: RuleSet, **params) -> 'RankingCalculator':
        """Create a calculator from a ruleset enum."""
        rule_class = cls.AVAILABLE_RULES[ruleset]
        rules = rule_class(**params)
        return cls(rules)
    
    @classmethod
    def from_config(cls, config_path: str) -> 'RankingCalculator':
        """Create a RankingCalculator from a configuration file."""
        with open(config_path) as f:
            config = json.load(f)
        
        # Import the rules class dynamically
        module_path = config['rules_module']
        class_name = config['rules_class']
        module = importlib.import_module(module_path)
        rules_class = getattr(module, class_name)
        
        # Initialize rules with optional parameters
        rules_params = config.get('rules_params', {})
        rules = rules_class(**rules_params)
        
        return cls(rules)
    
    def calculate_points(self, placement: int, competition_level: str) -> int:
        """Calculate points for a given placement and competition level."""
        if competition_level not in self.points_table:
            raise ValueError(f"Invalid competition level: {competition_level}")
            
        level_points = self.points_table[competition_level]
        return level_points.get(placement, 0)
    
    def calculate_season_ranking(self, results: List[CompetitionResult]) -> int:
        """Calculate season ranking based on the rules' best N results."""
        if not results:
            return 0
            
        sorted_results = sorted(results, key=lambda x: x.points, reverse=True)
        best_results = sorted_results[:self.best_n_results]
        return sum(result.points for result in best_results)
    
    def calculate_rankings(self, results: List[CompetitionResult], derogation_athletes: List[int] = None) -> Dict[str, List[Dict]]:
        """Calculate rankings for all categories based on the provided rules."""
        derogation_athletes = derogation_athletes or []
        
        # Group results by category
        category_results = {}
        for result in results:
            if result.category not in category_results:
                category_results[result.category] = []
            category_results[result.category].append(result)
        
        # Calculate rankings for each category
        rankings = {}
        for category, cat_results in category_results.items():
            category_rankings = []
            athlete_results = {}
            
            # Group results by athlete
            for result in cat_results:
                if result.athlete_id not in athlete_results:
                    athlete_results[result.athlete_id] = []
                athlete_results[result.athlete_id].append(result)
            
            # Calculate rankings for each athlete
            for athlete_id, results in athlete_results.items():
                total_points = self.calculate_season_ranking(results)
                category_rankings.append({
                    'athlete_id': athlete_id,
                    'points': total_points,
                    'original_points': total_points,
                    'num_competitions': len(results),
                    'best_result': min(r.placement for r in results),
                    'competitions_count': {
                        level: len([r for r in results if r.competition_level == level])
                        for level in self.points_table.keys()
                    },
                    'under_derogation': athlete_id in derogation_athletes
                })
            
            # Sort rankings by points
            category_rankings.sort(key=lambda x: x['points'], reverse=True)
            
            # Store original rankings before derogation handling
            for i, ranking in enumerate(category_rankings, 1):
                ranking['original_ranking'] = i
            
            # Handle derogations and redistribute points
            if derogation_athletes:
                category_rankings = self._handle_derogations(category_rankings)
            
            # Apply rule-specific tie handling
            rankings[category] = self.rules.handle_ties(category_rankings)
        
        return rankings
    
    def _handle_derogations(self, rankings: List[Dict]) -> List[Dict]:
        """Handle derogations and point redistribution."""
        derogation_config = self.rules.config.get('derogation', {})
        if not derogation_config.get('enabled', False):
            return rankings
        
        # First pass: identify derogation athletes and their points
        derogation_points = {}
        for ranking in rankings:
            if ranking['under_derogation']:
                derogation_points[ranking['athlete_id']] = {
                    'points': ranking['points'],
                    'ranking': ranking['original_ranking']
                }
                ranking['points'] = 0
                ranking['points_redistributed'] = True
        
        # Second pass: redistribute points
        if derogation_config['rules']['points_handling'] == 'redistribute':
            method = derogation_config['point_redistribution']['method']
            
            if method == 'next_athlete':
                # Sort by original ranking to maintain order
                rankings.sort(key=lambda x: x['original_ranking'])
                
                for i, ranking in enumerate(rankings):
                    if ranking['under_derogation']:
                        # Find next non-derogation athlete
                        next_athlete_idx = i + 1
                        while (next_athlete_idx < len(rankings) and 
                               rankings[next_athlete_idx]['under_derogation']):
                            next_athlete_idx += 1
                        
                        if next_athlete_idx < len(rankings):
                            # Give points to next athlete
                            next_athlete = rankings[next_athlete_idx]
                            next_athlete['points'] = derogation_points[ranking['athlete_id']]['points']
                            next_athlete['points_source_athlete'] = ranking['athlete_id']
                            next_athlete['points_source_ranking'] = ranking['original_ranking']
        
        # Final pass: update rankings
        # Sort by new points (derogation athletes will be at the end with 0 points)
        rankings.sort(key=lambda x: x['points'], reverse=True)
        
        # Update final rankings
        for i, ranking in enumerate(rankings, 1):
            ranking['ranking'] = i
            if ranking['under_derogation']:
                ranking['derogation_note'] = derogation_config['rules']['display_note']
        
        return rankings

    def check_qualification_criteria(self, athlete_results: List[CompetitionResult]) -> bool:
        """Check if an athlete meets qualification criteria based on the rules."""
        criteria = self.rules.get_qualification_criteria()
        
        if len(athlete_results) < criteria['min_competitions']:
            return False
        
        if 'min_provincial' in criteria:
            provincial_comps = len([r for r in athlete_results if r.competition_level == 'provincial'])
            if provincial_comps < criteria['min_provincial']:
                return False
        
        total_points = self.calculate_season_ranking(athlete_results)
        return total_points >= criteria['min_points']

def load_ruleset_config(ruleset_type: str) -> Dict:
    """Load ruleset configuration from JSON file."""
    config_path = os.path.join(
        os.path.dirname(__file__),
        'ranking_configs',
        f'{ruleset_type.lower()}.json'
    )
    with open(config_path, 'r') as f:
        return json.load(f) 