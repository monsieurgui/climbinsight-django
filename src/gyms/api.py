from ninja import Router, Schema
from ninja.security import HttpBearer
from typing import List, Optional
from django.shortcuts import get_object_or_404
from .models import Gym
from users.decorators import role_required

router = Router()

class GymSchema(Schema):
    name: str
    address: str
    city: str
    country: str
    contact_info: dict
    facilities: Optional[dict] = None
    operating_hours: Optional[dict] = None
    climbing_areas: Optional[List[dict]] = None

class GymOut(GymSchema):
    id: int
    is_active: bool

@router.get("/", response=List[GymOut])
def list_gyms(request, city: Optional[str] = None):
    """List all gyms with optional city filter."""
    gyms = Gym.objects.filter(is_active=True)
    if city:
        gyms = gyms.filter(city__icontains=city)
    return gyms

@router.get("/{gym_id}", response=GymOut)
def get_gym(request, gym_id: int):
    """Get detailed information about a specific gym."""
    return get_object_or_404(Gym, id=gym_id)

@router.post("/", response=GymOut)
@role_required(['ADMIN'])
def create_gym(request, payload: GymSchema):
    """Create a new gym."""
    gym = Gym.objects.create(**payload.dict())
    return gym

@router.put("/{gym_id}", response=GymOut)
@role_required(['ADMIN'])
def update_gym(request, gym_id: int, payload: GymSchema):
    """Update gym details."""
    gym = get_object_or_404(Gym, id=gym_id)
    for attr, value in payload.dict().items():
        setattr(gym, attr, value)
    gym.save()
    return gym

@router.delete("/{gym_id}")
@role_required(['ADMIN'])
def delete_gym(request, gym_id: int):
    """Delete a gym."""
    gym = get_object_or_404(Gym, id=gym_id)
    gym.is_active = False
    gym.save()
    return {"success": True} 