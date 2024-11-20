from ninja import Schema, ModelSchema
from typing import List, Dict, Optional
from datetime import date
from .models import League

class LeagueBase(Schema):
    name: str
    start_date: date
    end_date: date
    description: str = ""
    categories: List[str] = []
    ranking_system: Dict = {}
    qualification_criteria: Dict = {}
    governing_body: Optional[str] = None
    sanctioning_body: Optional[str] = None
    seasonal_statistics: Dict = {}
    historical_records: Dict = {}
    status: str = "draft"
    is_active: bool = True

class LeagueIn(Schema):
    name: str
    start_date: date
    end_date: date
    description: Optional[str] = ""
    categories: Optional[List[str]] = []
    status: Optional[str] = "draft"
    is_active: Optional[bool] = True
    
    # All other fields optional
    ranking_system: Optional[Dict] = {}
    qualification_criteria: Optional[Dict] = {}
    governing_body: Optional[str] = None
    sanctioning_body: Optional[str] = None
    seasonal_statistics: Optional[Dict] = {}
    historical_records: Optional[Dict] = {}

    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("End date must be after start date")

class LeagueOut(ModelSchema):
    id: int
    administrators: List[int] = []
    can_edit: bool = False
    can_delete: bool = False
    created_by_id: Optional[int] = None

    class Config:
        model = League
        model_fields = [
            'name', 'start_date', 'end_date', 'description', 
            'categories', 'status', 'is_active', 'governing_body',
            'sanctioning_body'
        ]

    @staticmethod
    def resolve_administrators(obj):
        return [user.id for user in obj.administrators.all()]

    @staticmethod
    def resolve_can_edit(obj, context):
        return obj.can_user_edit(context.request.auth)

    @staticmethod
    def resolve_can_delete(obj, context):
        return obj.can_user_delete(context.request.auth)

class LeagueSummary(Schema):
    total_competitions: int
    active_competitions: int
    total_participants: int
    categories_distribution: Dict[str, int]

class BulkLeagueIds(Schema):
    ids: List[int]

class LeagueUpdateSchema(Schema):
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None
    categories: Optional[List[str]] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None
    governing_body: Optional[str] = None
    sanctioning_body: Optional[str] = None
