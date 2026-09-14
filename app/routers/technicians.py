from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import RegionalCenter, Technician, UserRole
from app.schemas import TechnicianCreate, TechnicianOut, TechnicianWithNameOut

router = APIRouter(prefix="/technicians", tags=["technicians"])


@router.post("/", response_model=TechnicianOut)
def create_technician(
    payload: TechnicianCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN)),
):
    technician = Technician(**payload.model_dump())
    db.add(technician)
    db.commit()
    db.refresh(technician)
    return technician


@router.get("/", response_model=list[TechnicianOut])
def list_technicians(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return db.query(Technician).all()


@router.get("/available", response_model=list[TechnicianWithNameOut])
def list_available_technicians(
    regional_center_id: int | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(Technician).filter(Technician.is_available == True)
    if regional_center_id:
        query = query.filter(Technician.regional_center_id == regional_center_id)

    technicians = query.all()
    result = []
    for t in technicians:
        region = db.query(RegionalCenter).filter(RegionalCenter.id == t.regional_center_id).first()
        result.append(
            TechnicianWithNameOut(
                id=t.id,
                user_id=t.user_id,
                regional_center_id=t.regional_center_id,
                is_available=t.is_available,
                name=t.user.name,
                regional_center_name=region.name if region else None,
            )
        )
    return result