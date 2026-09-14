from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import RegionalCenter, UserRole
from app.schemas import RegionalCenterCreate, RegionalCenterOut

router = APIRouter(prefix="/regional-centers", tags=["regional-centers"])


@router.post("/", response_model=RegionalCenterOut)
def create_regional_center(
    payload: RegionalCenterCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN)),
):
    center = RegionalCenter(**payload.model_dump())
    db.add(center)
    db.commit()
    db.refresh(center)
    return center


@router.get("/", response_model=list[RegionalCenterOut])
def list_regional_centers(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return db.query(RegionalCenter).all()