from ninja import Schema
from datetime import date

class LeagueCreateSchema(Schema):
    name: str
    description: str
    start_date: date
    end_date: date

    def validate(self, data):
        if data['start_date'] > data['end_date']:
            raise ValueError("Start date must be before end date")
        return data
