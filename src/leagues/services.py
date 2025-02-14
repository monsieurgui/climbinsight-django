from typing import List, Dict, Optional
from datetime import date
from django.db import transaction
from django.db.models import Q
from django.core.cache import cache

from .models import League, LeagueRanking, Category
from competitions.models import Competition, CompetitionResult
from .ranking import RankingCalculator, CompetitionResult as RankingResult

class LeagueService:
    """Service layer for league operations."""
    
    def __init__(self, league: League):
        self.league = league
        self.ranking_calculator = RankingCalculator()
    
    def get_competition_results(self, category: Optional[Category] = None) -> List[RankingResult]:
        """Get all competition results for the league, optionally filtered by category."""
        # Try to get cached results
        cache_key = f"competition_results_{self.league.id}_{category.id if category else 'all'}"
        cached_results = cache.get(cache_key)
        
        if cached_results:
            return cached_results
            
        results_query = CompetitionResult.objects.filter(
            competition__league=self.league
        ).select_related('competition', 'athlete')
        
        if category:
            results_query = results_query.filter(category=category)
            
        results = []
        for result in results_query:
            results.append(RankingResult(
                placement=result.ranking,
                points=self.ranking_calculator.calculate_points(
                    result.ranking,
                    result.competition.level
                ),
                competition_level=result.competition.level,
                date=result.competition.start_date.date(),
                category=result.category.name
            ))
        
        # Cache results for 15 minutes
        cache.set(cache_key, results, timeout=900)
        
        return results
    
    @transaction.atomic
    def update_rankings(self, category: Optional[Category] = None):
        """Update rankings for the league, optionally for a specific category."""
        # Invalidate relevant caches
        cache_keys = [
            f"competition_results_{self.league.id}_{category.id if category else 'all'}",
            f"league_rankings_{self.league.id}_{category.name if category else 'all'}"
        ]
        cache.delete_many(cache_keys)
        
        # Get competition results
        results = self.get_competition_results(category)
        
        # Get derogation athletes
        derogation_athletes = list(self.league.derogation_athletes.values_list('id', flat=True))
        
        # Calculate new rankings
        rankings = self.ranking_calculator.calculate_rankings(results, derogation_athletes)
        
        # Update database
        for category_name, category_rankings in rankings.items():
            category_obj = Category.objects.get(name=category_name)
            
            # Delete existing rankings for this category
            LeagueRanking.objects.filter(
                league=self.league,
                category=category_obj
            ).delete()
            
            # Create new rankings
            for ranking in category_rankings:
                # Create base ranking object
                league_ranking = LeagueRanking.objects.create(
                    league=self.league,
                    athlete_id=ranking['athlete_id'],
                    category=category_obj,
                    points=ranking['points'],
                    ranking=ranking['ranking'],
                    competitions_attended=ranking['num_competitions'],
                    best_results={'best_placement': ranking['best_result']},
                    statistics={
                        'total_points': ranking['points'],
                        'average_points': ranking['points'] / ranking['num_competitions'] if ranking['num_competitions'] > 0 else 0,
                        'competitions_count': ranking['competitions_count']
                    }
                )
                
                # Add derogation-specific data if applicable
                if ranking.get('under_derogation'):
                    league_ranking.original_points = ranking['original_points']
                    league_ranking.original_ranking = ranking['original_ranking']
                    league_ranking.save()
                
                # Handle point redistribution
                if ranking.get('points_source_athlete'):
                    source_ranking = LeagueRanking.objects.get(
                        league=self.league,
                        category=category_obj,
                        athlete_id=ranking['points_source_athlete']
                    )
                    league_ranking.points_source = source_ranking
                    league_ranking.save()
        
        # Cache the new rankings
        cache_key = f"league_rankings_{self.league.id}_{category.name if category else 'all'}"
        cache.set(cache_key, rankings, timeout=900)  # Cache for 15 minutes
    
    def get_rankings(self, category: Optional[Category] = None) -> Dict:
        """Get current rankings, optionally filtered by category."""
        # Try to get cached rankings
        cache_key = f"league_rankings_{self.league.id}_{category.name if category else 'all'}"
        cached_rankings = cache.get(cache_key)
        
        if cached_rankings:
            return cached_rankings
            
        rankings_query = LeagueRanking.objects.filter(league=self.league)
        
        if category:
            rankings_query = rankings_query.filter(category=category)
            
        rankings_query = rankings_query.select_related('athlete', 'category')
        
        rankings = {}
        for ranking in rankings_query:
            category_name = ranking.category.name
            if category_name not in rankings:
                rankings[category_name] = []
                
            # Get formatted ranking data based on derogation status
            ranking_data = ranking.get_display_data()
            ranking_data['athlete'] = {
                'id': ranking.athlete.id,
                'name': f"{ranking.athlete.first_name} {ranking.athlete.last_name}",
                'email': ranking.athlete.email
            }
            
            rankings[category_name].append(ranking_data)
        
        # Cache rankings for 15 minutes
        cache.set(cache_key, rankings, timeout=900)
            
        return rankings
    
    def check_qualification_status(self, athlete_id: int, category: Category) -> Dict:
        """Check if an athlete meets qualification criteria for the category."""
        results = self.get_competition_results(category)
        athlete_results = [r for r in results if r.athlete_id == athlete_id]
        
        meets_criteria = self.ranking_calculator.check_qualification_criteria(
            athlete_results,
            min_competitions=self.league.qualification_criteria.get('min_competitions', 3),
            min_points=self.league.qualification_criteria.get('min_points', 50)
        )
        
        current_ranking = LeagueRanking.objects.filter(
            league=self.league,
            category=category,
            athlete_id=athlete_id
        ).first()
        
        return {
            'qualified': meets_criteria,
            'current_rank': current_ranking.ranking if current_ranking else None,
            'total_points': current_ranking.points if current_ranking else 0,
            'competitions_attended': len(athlete_results),
            'missing_requirements': {
                'competitions': max(0, self.league.qualification_criteria.get('min_competitions', 3) - len(athlete_results)),
                'points': max(0, self.league.qualification_criteria.get('min_points', 50) - (current_ranking.points if current_ranking else 0))
            }
        } 