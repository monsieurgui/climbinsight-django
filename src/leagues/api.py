from ninja import Router, Schema, Field, Query
from ninja.errors import HttpError
from typing import List, Optional
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from ninja_jwt.authentication import JWTAuth
from django.db.models import Q
from ninja.security import HttpBearer
from django.core.cache import cache
from django.conf import settings
from django.http import HttpResponse
import numpy as np
import scipy.stats as stats
import csv
import json
from io import StringIO
from datetime import datetime

from users.api import User, UserResponseSchema
from .models import League, Category, CompetitionResult, LeagueRanking
from competitions.api import CompetitionOut
from datetime import date
from .schemas import (
    LeagueOut, LeagueIn, BulkLeagueIds, LeagueUpdateSchema,
    LeagueSummary
)
from users.models import Role

router = Router(auth=JWTAuth())

class LeagueQuerySchema(Schema):
    status: Optional[str] = None
    is_active: Optional[bool] = None

class PaginationSchema(Schema):
    page: int = 1
    page_size: int = 20

class RankingVisualizationSchema(Schema):
    category_id: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    top_n: Optional[int] = 10
    page: Optional[int] = 1
    page_size: Optional[int] = 20

class RankingTimeSeriesSchema(Schema):
    athlete_id: int
    athlete_name: str
    dates: List[str]
    ranks: List[int]
    points: List[int]

class PointsDistributionSchema(Schema):
    ranges: List[str]
    counts: List[int]

class CompetitionLevelStatsSchema(Schema):
    level: str
    min_points: float
    max_points: float
    median_points: float
    q1_points: float
    q3_points: float

class AdvancedStatsSchema(Schema):
    athlete_id: int
    athlete_name: str
    consistency_score: float
    improvement_rate: float
    performance_vs_average: float
    level_distribution: dict
    streak_info: dict
    percentile_rank: float

class ExportFormatSchema(Schema):
    format: str = "csv"  # csv or json
    include_statistics: bool = True
    include_historical: bool = False
    category_id: Optional[int] = None

@router.get('', response=List[LeagueOut])
def list_leagues(request, query: LeagueQuerySchema = None):
    """
    Get a list of all leagues.
    
    Parameters:
        query: Optional query parameters for filtering
        - status: Filter by league status
        - is_active: Filter by active status
    
    Returns:
        List of leagues matching the query parameters
    """
    leagues = League.objects.all()
    if query:
        if query.status:
            leagues = leagues.filter(status=query.status)
        if query.is_active is not None:
            leagues = leagues.filter(is_active=query.is_active)
    return leagues

@router.post('', response={201: LeagueOut})
def create_league(request, payload: LeagueIn):
    """
    Create a new league.
    
    Parameters:
        payload: League creation data
        - name: League name
        - start_date: Start date
        - end_date: End date
        - description: Optional description
        - categories: List of category IDs
        
    Returns:
        Created league data
    """
    league = League.objects.create(
        name=payload.name,
        start_date=payload.start_date,
        end_date=payload.end_date,
        description=payload.description,
    )
    if payload.categories:
        league.categories.set(payload.categories)
    return league

@router.get('/{league_id}', response=LeagueOut)
def get_league(request, league_id: int):
    """
    Get details of a specific league.
    
    Parameters:
        league_id: ID of the league to retrieve
        
    Returns:
        League details
        
    Raises:
        404: League not found
    """
    return get_object_or_404(League, id=league_id)

@router.put('/{league_id}', response=LeagueOut)
def update_league(request, league_id: int, payload: LeagueUpdateSchema):
    """
    Update a league's details.
    
    Parameters:
        league_id: ID of the league to update
        payload: League update data
        - name: Optional new name
        - start_date: Optional new start date
        - end_date: Optional new end date
        - description: Optional new description
        - categories: Optional new list of category IDs
        
    Returns:
        Updated league data
        
    Raises:
        404: League not found
    """
    league = get_object_or_404(League, id=league_id)
    
    # Update fields if provided
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(league, field, value)
    
    league.save()
    return league

@router.delete('/{league_id}', response={204: None})
def delete_league(request, league_id: int):
    """
    Delete a league.
    
    Parameters:
        league_id: ID of the league to delete
        
    Returns:
        204: No content
        
    Raises:
        404: League not found
    """
    league = get_object_or_404(League, id=league_id)
    league.delete()
    return 204, None

@router.get('/{league_id}/summary', response=LeagueSummary)
def get_league_summary(request, league_id: int):
    """
    Get a summary of league statistics.
    
    Parameters:
        league_id: ID of the league
        
    Returns:
        League summary including:
        - Total competitions
        - Active competitions
        - Total participants
        - Category distribution
        
    Raises:
        404: League not found
    """
    league = get_object_or_404(League, id=league_id)
    return {
        'total_competitions': league.competitions.count(),
        'active_competitions': league.competitions.filter(is_active=True).count(),
        'total_participants': league.athletes.count(),
        'categories_distribution': {
            cat.name: cat.competitions.filter(league=league).count()
            for cat in league.categories.all()
        }
    }

@router.post('/bulk-delete', response={204: None})
def bulk_delete_leagues(request, payload: BulkLeagueIds):
    """
    Delete multiple leagues at once.
    
    Parameters:
        payload: List of league IDs to delete
        
    Returns:
        204: No content
    """
    League.objects.filter(id__in=payload.ids).delete()
    return 204, None

@router.get("/{league_id}/competitions", response=List[CompetitionOut])
def get_league_competitions(request, league_id: int):
    league = get_object_or_404(League, id=league_id)
    return league.competitions.all()

@router.post("/bulk-activate", response=dict)
def bulk_activate_leagues(request, payload: BulkLeagueIds):
    updated = League.objects.filter(id__in=payload.ids).update(is_active=True)
    return {"updated": updated}

@router.post("/bulk-deactivate", response=dict)
def bulk_deactivate_leagues(request, payload: BulkLeagueIds):
    updated = League.objects.filter(id__in=payload.ids).update(is_active=False)
    return {"updated": updated}

@router.get("/{league_id}/athletes", response=List[UserResponseSchema])
def get_league_athletes(request, league_id: int):
    """Get all athletes registered in a league"""
    league = get_object_or_404(League, id=league_id)
    return league.athletes.all()

@router.post("/{league_id}/athletes/{user_id}")
def add_athlete_to_league(request, league_id: int, user_id: int):
    """Add an athlete to a league"""
    league = get_object_or_404(League, id=league_id)
    user = get_object_or_404(User, id=user_id)
    league.athletes.add(user)
    return {"success": True}

@router.delete("/{league_id}/athletes/{user_id}")
def remove_athlete_from_league(request, league_id: int, user_id: int):
    """Remove an athlete from a league"""
    league = get_object_or_404(League, id=league_id)
    user = get_object_or_404(User, id=user_id)
    league.athletes.remove(user)
    return {"success": True}

@router.get("/{league_id}/officials", response=List[UserResponseSchema])
def get_league_officials(request, league_id: int):
    """Get all officials assigned to a league"""
    league = get_object_or_404(League, id=league_id)
    return league.officials.all()

@router.post("/{league_id}/officials/{user_id}")
def add_official_to_league(request, league_id: int, user_id: int):
    """Add an official to a league"""
    league = get_object_or_404(League, id=league_id)
    user = get_object_or_404(User, id=user_id)
    if not user.has_role('official'):
        return {"error": "User is not an official"}, 400
    league.officials.add(user)
    return {"success": True}

@router.get("/{league_id}/rankings", response=dict)
def get_league_rankings(request, league_id: int, category: Optional[str] = None, pagination: PaginationSchema = Query(...)):
    """Get league rankings, optionally filtered by category with pagination"""
    # Try to get cached rankings
    cache_key = f"league_rankings_{league_id}_{category}_{pagination.page}_{pagination.page_size}"
    cached_rankings = cache.get(cache_key)
    
    if cached_rankings:
        return cached_rankings
        
    league = get_object_or_404(League, id=league_id)
    rankings = league.get_current_rankings(category)
    
    # Paginate the results
    start_idx = (pagination.page - 1) * pagination.page_size
    end_idx = start_idx + pagination.page_size
    
    # Calculate total pages
    total_items = len(rankings)
    total_pages = (total_items + pagination.page_size - 1) // pagination.page_size
    
    paginated_rankings = {
        'data': rankings[start_idx:end_idx],
        'pagination': {
            'current_page': pagination.page,
            'total_pages': total_pages,
            'total_items': total_items,
            'page_size': pagination.page_size
        }
    }
    
    # Cache the results for 5 minutes
    cache.set(cache_key, paginated_rankings, timeout=300)
    
    return paginated_rankings

@router.post("/{league_id}/rankings")
def update_league_rankings(request, league_id: int, rankings: dict, category: Optional[str] = None):
    """Update league rankings"""
    league = get_object_or_404(League, id=league_id)
    league.update_rankings(rankings, category)
    return {"success": True}

@router.get("/{league_id}/rankings/timeseries", response=List[RankingTimeSeriesSchema])
def get_rankings_timeseries(request, league_id: int, params: RankingVisualizationSchema = Query(...)):
    """Get time series data of rankings for visualization."""
    # Try to get cached data
    cache_key = f"rankings_timeseries_{league_id}_{params.category_id}_{params.start_date}_{params.end_date}_{params.top_n}"
    cached_data = cache.get(cache_key)
    
    if cached_data:
        return cached_data
        
    league = get_object_or_404(League, id=league_id)
    
    # Get competition results
    results = CompetitionResult.objects.filter(
        competition__league=league
    ).select_related('competition', 'athlete')
    
    if params.category_id:
        results = results.filter(category_id=params.category_id)
    
    if params.start_date:
        results = results.filter(competition__start_date__gte=params.start_date)
    if params.end_date:
        results = results.filter(competition__start_date__lte=params.end_date)
    
    # Group by athlete and get top athletes by points
    athlete_points = {}
    for result in results:
        athlete_id = result.athlete.id
        if athlete_id not in athlete_points:
            athlete_points[athlete_id] = 0
        athlete_points[athlete_id] += result.points
    
    top_athletes = sorted(athlete_points.items(), key=lambda x: x[1], reverse=True)[:params.top_n]
    top_athlete_ids = [a[0] for a in top_athletes]
    
    # Prepare time series data
    timeseries_data = []
    for athlete_id in top_athlete_ids:
        athlete_results = results.filter(athlete_id=athlete_id).order_by('competition__start_date')
        athlete = athlete_results.first().athlete
        
        timeseries_data.append({
            'athlete_id': athlete_id,
            'athlete_name': f"{athlete.first_name} {athlete.last_name}",
            'dates': [r.competition.start_date.isoformat() for r in athlete_results],
            'ranks': [r.ranking for r in athlete_results],
            'points': [r.points for r in athlete_results]
        })
    
    # Cache the results for 10 minutes
    cache.set(cache_key, timeseries_data, timeout=600)
    
    return timeseries_data

@router.get("/{league_id}/rankings/distribution", response=PointsDistributionSchema)
def get_points_distribution(request, league_id: int, params: RankingVisualizationSchema = Query(...)):
    """Get distribution of points for visualization."""
    league = get_object_or_404(League, id=league_id)
    
    # Get current rankings
    rankings = LeagueRanking.objects.filter(league=league)
    if params.category_id:
        rankings = rankings.filter(category_id=params.category_id)
    
    points = [r.points for r in rankings]
    
    # Create histogram data
    hist, bins = np.histogram(points, bins=20)
    ranges = [f"{int(bins[i])}-{int(bins[i+1])}" for i in range(len(bins)-1)]
    
    return {
        'ranges': ranges,
        'counts': hist.tolist()
    }

@router.get("/{league_id}/rankings/level-stats", response=List[CompetitionLevelStatsSchema])
def get_competition_level_stats(request, league_id: int, params: RankingVisualizationSchema = Query(...)):
    """Get statistics by competition level for visualization."""
    league = get_object_or_404(League, id=league_id)
    
    # Get competition results
    results = CompetitionResult.objects.filter(
        competition__league=league
    ).select_related('competition')
    
    if params.category_id:
        results = results.filter(category_id=params.category_id)
    
    # Group by competition level and calculate stats
    level_stats = []
    for level in results.values_list('competition__ruleset__level', flat=True).distinct():
        level_results = results.filter(competition__ruleset__level=level)
        points = [r.points for r in level_results]
        
        if points:
            level_stats.append({
                'level': level,
                'min_points': float(np.min(points)),
                'max_points': float(np.max(points)),
                'median_points': float(np.median(points)),
                'q1_points': float(np.percentile(points, 25)),
                'q3_points': float(np.percentile(points, 75))
            })
    
    return level_stats

@router.get("/{league_id}/rankings/summary", response=dict)
def get_rankings_summary(request, league_id: int, params: RankingVisualizationSchema = Query(...)):
    """Get summary statistics of rankings."""
    league = get_object_or_404(League, id=league_id)
    
    # Get current rankings
    rankings = LeagueRanking.objects.filter(league=league)
    if params.category_id:
        rankings = rankings.filter(category_id=params.category_id)
    
    points = [r.points for r in rankings]
    competitions = [r.competitions_attended for r in rankings]
    
    # Calculate standard deviation for consistency measure
    points_std = float(np.std(points)) if points else 0
    
    # Calculate skewness and kurtosis for distribution shape
    points_skew = float(stats.skew(points)) if points else 0
    points_kurtosis = float(stats.kurtosis(points)) if points else 0
    
    return {
        'total_athletes': len(rankings),
        'average_points': float(np.mean(points)) if points else 0,
        'median_points': float(np.median(points)) if points else 0,
        'max_points': float(np.max(points)) if points else 0,
        'min_points': float(np.min(points)) if points else 0,
        'average_competitions': float(np.mean(competitions)) if competitions else 0,
        'points_distribution': {
            'top_10': float(np.percentile(points, 90)) if points else 0,
            'top_25': float(np.percentile(points, 75)) if points else 0,
            'median': float(np.percentile(points, 50)) if points else 0,
            'bottom_25': float(np.percentile(points, 25)) if points else 0,
            'bottom_10': float(np.percentile(points, 10)) if points else 0
        },
        'advanced_metrics': {
            'standard_deviation': points_std,
            'coefficient_of_variation': points_std / float(np.mean(points)) if points and np.mean(points) != 0 else 0,
            'skewness': points_skew,
            'kurtosis': points_kurtosis,
            'interquartile_range': float(np.percentile(points, 75) - np.percentile(points, 25)) if points else 0,
            'competition_frequency': {
                'average_gap': float(np.mean(np.diff(sorted(competitions)))) if len(competitions) > 1 else 0,
                'max_gap': float(np.max(np.diff(sorted(competitions)))) if len(competitions) > 1 else 0
            }
        }
    }

@router.get("/{league_id}/rankings/advanced-stats", response=List[AdvancedStatsSchema])
def get_advanced_stats(request, league_id: int, params: RankingVisualizationSchema = Query(...)):
    """Get advanced statistics for athletes."""
    league = get_object_or_404(League, id=league_id)
    
    # Get competition results
    results = CompetitionResult.objects.filter(
        competition__league=league
    ).select_related('competition', 'athlete')
    
    if params.category_id:
        results = results.filter(category_id=params.category_id)
    
    # Group results by athlete
    athlete_stats = {}
    for result in results:
        athlete_id = result.athlete.id
        if athlete_id not in athlete_stats:
            athlete_stats[athlete_id] = {
                'athlete_id': athlete_id,
                'athlete_name': f"{result.athlete.first_name} {result.athlete.last_name}",
                'points': [],
                'rankings': [],
                'levels': [],
                'dates': []
            }
        athlete_stats[athlete_id]['points'].append(result.points)
        athlete_stats[athlete_id]['rankings'].append(result.ranking)
        athlete_stats[athlete_id]['levels'].append(result.competition.level)
        athlete_stats[athlete_id]['dates'].append(result.competition.start_date)
    
    # Calculate advanced statistics for each athlete
    advanced_stats = []
    for athlete_id, stats in athlete_stats.items():
        if len(stats['points']) < 2:  # Skip athletes with insufficient data
            continue
            
        # Calculate consistency score (inverse of coefficient of variation)
        points_std = np.std(stats['points'])
        points_mean = np.mean(stats['points'])
        consistency_score = 1 - (points_std / points_mean) if points_mean != 0 else 0
        
        # Calculate improvement rate (linear regression slope)
        dates_numeric = [(d - min(stats['dates'])).days for d in stats['dates']]
        if len(dates_numeric) > 1:
            slope = np.polyfit(dates_numeric, stats['points'], 1)[0]
            improvement_rate = slope * 30  # Points improvement per month
        else:
            improvement_rate = 0
        
        # Calculate performance vs average
        all_points = [r.points for r in results]
        avg_points = np.mean(all_points) if all_points else 0
        performance_vs_average = (np.mean(stats['points']) - avg_points) / avg_points if avg_points != 0 else 0
        
        # Calculate level distribution
        level_counts = {}
        for level in stats['levels']:
            level_counts[level] = level_counts.get(level, 0) + 1
        
        # Calculate streaks
        rankings = stats['rankings']
        current_streak = 1
        best_streak = 1
        for i in range(1, len(rankings)):
            if rankings[i] <= rankings[i-1]:
                current_streak += 1
                best_streak = max(best_streak, current_streak)
            else:
                current_streak = 1
        
        # Calculate percentile rank
        percentile_rank = stats.percentileofscore(all_points, np.mean(stats['points']))
        
        advanced_stats.append({
            'athlete_id': stats['athlete_id'],
            'athlete_name': stats['athlete_name'],
            'consistency_score': float(consistency_score),
            'improvement_rate': float(improvement_rate),
            'performance_vs_average': float(performance_vs_average),
            'level_distribution': level_counts,
            'streak_info': {
                'current_streak': current_streak,
                'best_streak': best_streak
            },
            'percentile_rank': float(percentile_rank)
        })
    
    return advanced_stats

@router.get("/{league_id}/export/rankings")
def export_rankings(request, league_id: int, params: ExportFormatSchema = Query(...)):
    """Export rankings data in CSV or JSON format."""
    league = get_object_or_404(League, id=league_id)
    
    # Get rankings data
    rankings = LeagueRanking.objects.filter(league=league)
    if params.category_id:
        rankings = rankings.filter(category_id=params.category_id)
    
    rankings = rankings.select_related('athlete', 'category')
    
    if params.format.lower() == "csv":
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="rankings_{league.name}_{datetime.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        
        # Write headers
        headers = ['Athlete ID', 'Name', 'Category', 'Rank', 'Points', 'Competitions Attended']
        if params.include_statistics:
            headers.extend(['Average Points', 'Best Result', 'Consistency Score'])
        writer.writerow(headers)
        
        # Write data
        for ranking in rankings:
            row = [
                ranking.athlete.id,
                f"{ranking.athlete.first_name} {ranking.athlete.last_name}",
                ranking.category.name,
                ranking.ranking,
                ranking.points,
                ranking.competitions_attended
            ]
            if params.include_statistics:
                stats = ranking.statistics
                row.extend([
                    stats.get('average_points', 0),
                    ranking.best_results.get('best_placement', 'N/A'),
                    stats.get('consistency_score', 0)
                ])
            writer.writerow(row)
        
        return response
    else:
        # Create JSON response
        data = {
            'league': league.name,
            'export_date': datetime.now().isoformat(),
            'rankings': []
        }
        
        for ranking in rankings:
            ranking_data = {
                'athlete': {
                    'id': ranking.athlete.id,
                    'name': f"{ranking.athlete.first_name} {ranking.athlete.last_name}"
                },
                'category': ranking.category.name,
                'rank': ranking.ranking,
                'points': ranking.points,
                'competitions_attended': ranking.competitions_attended
            }
            
            if params.include_statistics:
                ranking_data['statistics'] = ranking.statistics
                ranking_data['best_results'] = ranking.best_results
            
            data['rankings'].append(ranking_data)
        
        response = HttpResponse(json.dumps(data, indent=2), content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="rankings_{league.name}_{datetime.now().strftime("%Y%m%d")}.json"'
        return response

@router.get("/{league_id}/export/statistics")
def export_statistics(request, league_id: int, params: ExportFormatSchema = Query(...)):
    """Export detailed statistics in CSV or JSON format."""
    league = get_object_or_404(League, id=league_id)
    
    # Get advanced statistics
    advanced_stats = get_advanced_stats(request, league_id, RankingVisualizationSchema(
        category_id=params.category_id
    ))
    
    if params.format.lower() == "csv":
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="statistics_{league.name}_{datetime.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        
        # Write headers
        headers = [
            'Athlete ID', 'Name', 'Consistency Score', 'Improvement Rate',
            'Performance vs Average', 'Current Streak', 'Best Streak',
            'Percentile Rank'
        ]
        writer.writerow(headers)
        
        # Write data
        for stat in advanced_stats:
            writer.writerow([
                stat['athlete_id'],
                stat['athlete_name'],
                stat['consistency_score'],
                stat['improvement_rate'],
                stat['performance_vs_average'],
                stat['streak_info']['current_streak'],
                stat['streak_info']['best_streak'],
                stat['percentile_rank']
            ])
        
        return response
    else:
        # Create JSON response with full data
        data = {
            'league': league.name,
            'export_date': datetime.now().isoformat(),
            'statistics': advanced_stats
        }
        
        response = HttpResponse(json.dumps(data, indent=2), content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="statistics_{league.name}_{datetime.now().strftime("%Y%m%d")}.json"'
        return response

@router.get("/ping")
def ping(request):
    """Test endpoint to verify router is mounted"""
    return {"message": "leagues router is responding"}