from datetime import datetime

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.models import (
    Assignment,
    Customer,
    Job,
    Jobsheet,
    JobStatus,
    Location,
    Notification,
    RegionalCenter,
    Technician,
    User,
    UserRole,
)
from app.services.location_service import haversine_distance_km
from app.services.push_service import send_push_notification

MAX_JOBSHEET_SIZE_BYTES = 8 * 1024 * 1024  # 8 MB


def assign_technician_to_job(job_id: int, db: Session) -> Assignment:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.CREATED:
        raise HTTPException(status_code=400, detail="Job is not in a state that can be assigned")
    if not job.regional_center_id:
        raise HTTPException(status_code=400, detail="Job has no regional center set")

    technician = (
        db.query(Technician)
        .filter(
            Technician.regional_center_id == job.regional_center_id,
            Technician.is_available == True,
        )
        .first()
    )
    if not technician:
        raise HTTPException(status_code=404, detail="No available technician found in this regional center")

    return _create_assignment(job, technician, db)


def assign_specific_technician_to_job(job_id: int, technician_id: int, db: Session) -> Assignment:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in (JobStatus.CREATED, JobStatus.ASSIGNED):
        raise HTTPException(
            status_code=400,
            detail="Technicians can only be assigned before the job has started",
        )

    technician = db.query(Technician).filter(Technician.id == technician_id).first()
    if not technician:
        raise HTTPException(status_code=404, detail="Technician not found")
    if not technician.is_available:
        raise HTTPException(status_code=400, detail="This technician is not currently available")

    existing = (
        db.query(Assignment)
        .filter(
            Assignment.job_id == job.id,
            Assignment.technician_id == technician.id,
            Assignment.status == "active",
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="This technician is already assigned to this job")

    return _create_assignment(job, technician, db)


def _create_assignment(job: Job, technician: Technician, db: Session) -> Assignment:
    assignment = Assignment(job_id=job.id, technician_id=technician.id, status="active")
    db.add(assignment)

    technician.is_available = False
    job.status = JobStatus.ASSIGNED

    notification = Notification(
        job_id=job.id,
        technician_id=technician.id,
        message=f"New job assigned: {job.job_number}",
    )
    db.add(notification)

    db.commit()
    db.refresh(assignment)

    send_push_notification(
        technician.user.push_token,
        "New Job Assigned",
        f"You've been assigned to job {job.job_number}",
        {"job_id": job.id},
    )

    return assignment


def _get_active_assignments(job_id: int, db: Session) -> list[Assignment]:
    return (
        db.query(Assignment)
        .filter(Assignment.job_id == job_id, Assignment.status == "active")
        .all()
    )


def _get_my_active_assignment(job_id: int, current_user: User, db: Session) -> Assignment | None:
    technician = db.query(Technician).filter(Technician.user_id == current_user.id).first()
    if not technician:
        return None
    return (
        db.query(Assignment)
        .filter(
            Assignment.job_id == job_id,
            Assignment.technician_id == technician.id,
            Assignment.status == "active",
        )
        .first()
    )


def get_assigned_technicians(job_id: int, db: Session) -> list[dict]:
    """Returns everyone currently or previously working this job (excludes cancelled assignments),
    each with their OWN started_at so the app can show individual progress."""
    assignments = (
        db.query(Assignment)
        .filter(Assignment.job_id == job_id, Assignment.status.in_(["active", "completed"]))
        .all()
    )

    result = []
    for a in assignments:
        technician = db.query(Technician).filter(Technician.id == a.technician_id).first()
        if not technician:
            continue
        region = db.query(RegionalCenter).filter(RegionalCenter.id == technician.regional_center_id).first()
        result.append(
            {
                "id": technician.id,
                "user_id": technician.user_id,
                "name": technician.user.name,
                "regional_center_name": region.name if region else None,
                "status": a.status,
                "started_at": a.started_at,
            }
        )
    return result


def cancel_job(job_id: int, db: Session) -> Job:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in (JobStatus.CREATED, JobStatus.ASSIGNED):
        raise HTTPException(
            status_code=400,
            detail="Only jobs that are not yet started can be cancelled",
        )

    for active_assignment in _get_active_assignments(job.id, db):
        technician = db.query(Technician).filter(Technician.id == active_assignment.technician_id).first()
        if technician:
            technician.is_available = True
        active_assignment.status = "cancelled"
        active_assignment.unassigned_at = datetime.utcnow()

    job.status = JobStatus.CANCELLED
    db.commit()
    db.refresh(job)
    return job


def admin_close_job(job_id: int, reason: str, db: Session) -> Job:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in (JobStatus.ASSIGNED, JobStatus.STARTED):
        raise HTTPException(
            status_code=400,
            detail="Only jobs that are assigned or started can be force-closed by an admin",
        )

    technician_names = []
    for active_assignment in _get_active_assignments(job.id, db):
        technician = db.query(Technician).filter(Technician.id == active_assignment.technician_id).first()
        if technician:
            technician.is_available = True
            technician_names.append(technician.user.name)
        active_assignment.status = "completed"
        active_assignment.unassigned_at = datetime.utcnow()

    job.status = JobStatus.CLOSED
    job.closed_at = datetime.utcnow()
    job.closed_reason = reason
    job.closed_by_admin = True

    _notify_admins_job_closed(job, technician_names, f"Job force-closed ({reason})", db)

    db.commit()
    db.refresh(job)
    return job


def _notify_admins_job_closed(job: Job, technician_names: list[str], extra_context: str, db: Session) -> None:
    customer = db.query(Customer).filter(Customer.id == job.customer_id).first()
    summary = calculate_job_summary(job, db)

    duration_text = f"{summary['duration_hours']}h" if summary["duration_hours"] is not None else "N/A"
    distance_text = f"{summary['total_distance_km']} km" if summary["total_distance_km"] is not None else "N/A"
    tech_text = ", ".join(technician_names) if technician_names else "Unassigned"

    message = (
        f"{extra_context} — {job.job_number} | "
        f"Customer: {customer.name if customer else 'Unknown'} | "
        f"Technician(s): {tech_text} | "
        f"Time: {duration_text} | Distance: {distance_text}"
    )

    admins = db.query(User).filter(User.role == UserRole.ADMIN).all()
    for admin in admins:
        db.add(Notification(job_id=job.id, recipient_admin_id=admin.id, message=message))
        send_push_notification(
            admin.push_token,
            "Job Closed",
            f"{job.job_number} — {tech_text} — {duration_text}, {distance_text}",
            {"job_id": job.id},
        )


def calculate_job_summary(job: Job, db: Session) -> dict:
    """Returns total duration (hours) and total distance traveled (km) for a job,
    computed from started_at/closed_at and the recorded GPS trail."""
    duration_hours = None
    if job.started_at and job.closed_at:
        duration_hours = round((job.closed_at - job.started_at).total_seconds() / 3600, 2)

    locations = (
        db.query(Location)
        .filter(Location.job_id == job.id)
        .order_by(Location.recorded_at.asc())
        .all()
    )

    total_km = None
    if len(locations) > 1:
        total = 0.0
        for i in range(1, len(locations)):
            total += haversine_distance_km(
                locations[i - 1].latitude,
                locations[i - 1].longitude,
                locations[i].latitude,
                locations[i].longitude,
            )
        total_km = round(total, 2)

    return {"duration_hours": duration_hours, "total_distance_km": total_km}


def start_job(job_id: int, current_user: User, db: Session) -> Job:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in (JobStatus.ASSIGNED, JobStatus.STARTED):
        raise HTTPException(status_code=400, detail="Job is not in a state that can be started")

    my_assignment = _get_my_active_assignment(job_id, current_user, db)
    if not my_assignment:
        raise HTTPException(status_code=403, detail="You are not assigned to this job")
    if my_assignment.started_at is not None:
        raise HTTPException(status_code=400, detail="You have already started this job")

    my_assignment.started_at = datetime.utcnow()

    if job.status == JobStatus.ASSIGNED:
        job.status = JobStatus.STARTED
        job.started_at = datetime.utcnow()

    db.commit()
    db.refresh(job)
    return job


def upload_jobsheet_and_close(job_id: int, file: UploadFile, current_user: User, db: Session) -> Jobsheet:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.STARTED:
        raise HTTPException(status_code=400, detail="Job must be started before uploading a job sheet")

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    my_assignment = _get_my_active_assignment(job_id, current_user, db)
    if not my_assignment:
        raise HTTPException(status_code=403, detail="You are not assigned to this job")

    file_bytes = file.file.read()
    if len(file_bytes) > MAX_JOBSHEET_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File is too large (max 8 MB)")

    jobsheet = Jobsheet(
        job_id=job.id,
        filename=file.filename or "jobsheet.pdf",
        content_type=file.content_type,
        file_data=file_bytes,
    )
    db.add(jobsheet)

    job.status = JobStatus.CLOSED
    job.closed_at = datetime.utcnow()

    technician_names = []
    for active_assignment in _get_active_assignments(job.id, db):
        technician = db.query(Technician).filter(Technician.id == active_assignment.technician_id).first()
        if technician:
            technician.is_available = True
            technician_names.append(technician.user.name)
        active_assignment.status = "completed"
        active_assignment.unassigned_at = datetime.utcnow()

    _notify_admins_job_closed(job, technician_names, "Job sheet uploaded", db)

    db.commit()
    db.refresh(jobsheet)
    return jobsheet


def record_location(job_id: int, latitude: float, longitude: float, current_user: User, db: Session) -> Location:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in (JobStatus.ASSIGNED, JobStatus.STARTED):
        raise HTTPException(status_code=400, detail="Location can only be recorded for an active job")

    my_assignment = _get_my_active_assignment(job_id, current_user, db)
    if not my_assignment:
        raise HTTPException(status_code=403, detail="You are not assigned to this job")

    location = Location(
        job_id=job.id,
        technician_id=my_assignment.technician_id,
        latitude=latitude,
        longitude=longitude,
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


def get_job_locations(job_id: int, db: Session) -> list[Location]:
    return (
        db.query(Location)
        .filter(Location.job_id == job_id)
        .order_by(Location.recorded_at.asc())
        .all()
    )