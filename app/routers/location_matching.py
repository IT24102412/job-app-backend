from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas import RegionalCenterOut
from app.services.location_service import find_nearest_regional_center

router = APIRouter(prefix="/location-matching", tags=["location-matching"])


@router.get("/nearest-center", response_model=RegionalCenterOut | None)
def get_nearest_center(
    latitude: float,
    longitude: float,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return find_nearest_regional_center(latitude, longitude, db)