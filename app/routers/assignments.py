from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_role
from app.models import UserRole
from app.schemas import AssignmentOut, TechnicianRecommendationOut
from app.services.assignment_service import assign_specific_technician_to_job, assign_technician_to_job
from app.services.recommendation_service import recommend_technicians

router = APIRouter(prefix="/assignments", tags=["assignments"])


@router.post("/jobs/{job_id}/assign", response_model=AssignmentOut)
def assign_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN)),
):
    return assign_technician_to_job(job_id, db)


@router.post("/jobs/{job_id}/assign-technician/{technician_id}", response_model=AssignmentOut)
def assign_specific_technician(
    job_id: int,
    technician_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN)),
):
    return assign_specific_technician_to_job(job_id, technician_id, db)


@router.get("/jobs/{job_id}/recommendations", response_model=list[TechnicianRecommendationOut])
def get_technician_recommendations(
    job_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN)),
):
    return recommend_technicians(job_id, db)