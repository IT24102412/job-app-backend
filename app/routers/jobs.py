from datetime import datetime
from calendar import monthrange

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import Assignment, Job, Jobsheet, JobStatus, ServiceType, Technician, User, UserRole
from app.schemas import (
    AdminCloseJobRequest,
    AssignedTechnicianOut,
    JobCreate,
    JobOut,
    JobSummaryOut,
    JobsheetOut,
    LocationCreate,
    LocationOut,
)
from app.services.assignment_service import (
    admin_close_job,
    calculate_job_summary,
    cancel_job,
    get_assigned_technicians,
    get_job_locations,
    record_location,
    start_job,
    upload_jobsheet_and_close,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])

ALLOWED_ATTACHMENT_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/jpg"}
MAX_FILE_SIZE_BYTES = 8 * 1024 * 1024  # 8 MB


@router.post("/", response_model=JobOut)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.SALES_EXECUTIVE, UserRole.ADMIN)),
):
    import uuid

    temp_placeholder = f"TEMP-{uuid.uuid4().hex[:12]}"
    job = Job(**payload.model_dump(), job_number=temp_placeholder)
    db.add(job)
    db.flush()

    job.job_number = f"{payload.request_type.value}-{job.id:06d}"

    db.commit()
    db.refresh(job)
    return job


@router.get("/", response_model=list[JobOut])
def list_jobs(
    status: JobStatus | None = None,
    service_type: ServiceType | None = None,
    regional_center_id: int | None = None,
    year: int | None = None,
    month: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.TECHNICIAN:
        technician = db.query(Technician).filter(Technician.user_id == current_user.id).first()
        if not technician:
            return []
        job_ids = (
            db.query(Assignment.job_id)
            .filter(Assignment.technician_id == technician.id)
            .distinct()
        )
        query = db.query(Job).filter(Job.id.in_(job_ids))
    else:
        query = db.query(Job)

    if status:
        query = query.filter(Job.status == status)
    if service_type:
        query = query.filter(Job.service_type == service_type)
    if regional_center_id:
        query = query.filter(Job.regional_center_id == regional_center_id)
    if year and month:
        start_date = datetime(year, month, 1)
        last_day = monthrange(year, month)[1]
        end_date = datetime(year, month, last_day, 23, 59, 59)
        query = query.filter(Job.created_at >= start_date, Job.created_at <= end_date)

    return query.all()


@router.get("/{job_id}/summary", response_model=JobSummaryOut)
def get_job_summary(
    job_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return calculate_job_summary(job, db)


@router.get("/{job_id}/assigned-technicians", response_model=list[AssignedTechnicianOut])
def get_job_assigned_technicians(
    job_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return get_assigned_technicians(job_id, db)


@router.post("/{job_id}/upload-attachment", response_model=JobOut)
def upload_sr_attachment(
    job_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.SALES_EXECUTIVE, UserRole.ADMIN)),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if file.content_type not in ALLOWED_ATTACHMENT_TYPES:
        raise HTTPException(status_code=400, detail="Only PDF or image files (JPEG/PNG) are allowed")

    file_bytes = file.file.read()
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File is too large (max 8 MB)")

    job.sr_attachment_filename = file.filename or "attachment"
    job.sr_attachment_content_type = file.content_type
    job.sr_attachment_data = file_bytes

    db.commit()
    db.refresh(job)
    return job


@router.get("/{job_id}/attachment")
def download_sr_attachment(
    job_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.sr_attachment_data:
        raise HTTPException(status_code=404, detail="No attachment found for this job")

    return Response(
        content=job.sr_attachment_data,
        media_type=job.sr_attachment_content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{job.sr_attachment_filename}"'},
    )


@router.get("/{job_id}/jobsheet")
def download_jobsheet(
    job_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    jobsheet = (
        db.query(Jobsheet)
        .filter(Jobsheet.job_id == job_id)
        .order_by(Jobsheet.uploaded_at.desc())
        .first()
    )
    if not jobsheet:
        raise HTTPException(status_code=404, detail="No job sheet found for this job")

    return Response(
        content=jobsheet.file_data,
        media_type=jobsheet.content_type,
        headers={"Content-Disposition": f'attachment; filename="{jobsheet.filename}"'},
    )


@router.post("/{job_id}/start", response_model=JobOut)
def start_job_endpoint(
    job_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return start_job(job_id, current_user, db)


@router.post("/{job_id}/cancel", response_model=JobOut)
def cancel_job_endpoint(
    job_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN)),
):
    return cancel_job(job_id, db)


@router.post("/{job_id}/admin-close", response_model=JobOut)
def admin_close_job_endpoint(
    job_id: int,
    payload: AdminCloseJobRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN)),
):
    return admin_close_job(job_id, payload.reason, db)


@router.post("/{job_id}/upload-jobsheet", response_model=JobsheetOut)
def upload_jobsheet_endpoint(
    job_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return upload_jobsheet_and_close(job_id, file, current_user, db)


@router.post("/{job_id}/location", response_model=LocationOut)
def record_location_endpoint(
    job_id: int,
    payload: LocationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return record_location(job_id, payload.latitude, payload.longitude, current_user, db)


@router.get("/{job_id}/locations", response_model=list[LocationOut])
def get_job_locations_endpoint(
    job_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return get_job_locations(job_id, db)