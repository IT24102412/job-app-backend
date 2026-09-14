from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Assignment, Job, JobStatus, Technician
from app.services.location_service import haversine_distance_km

AVERAGE_SPEED_KMH = 30  # rough average for local roads, used only for a time estimate


def recommend_technicians(job_id: int, db: Session) -> list[dict]:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.regional_center_id:
        raise HTTPException(status_code=400, detail="Job has no regional center set")

    customer = job.customer

    technicians = (
        db.query(Technician)
        .filter(
            Technician.regional_center_id == job.regional_center_id,
            Technician.is_available == True,
        )
        .all()
    )

    if not technicians:
        return []

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    results = []
    for tech in technicians:
        distance_km = haversine_distance_km(
            customer.latitude, customer.longitude, tech.regional_center.latitude, tech.regional_center.longitude
        )

        experience_count = (
            db.query(Assignment)
            .join(Job, Assignment.job_id == Job.id)
            .filter(
                Assignment.technician_id == tech.id,
                Job.service_type == job.service_type,
                Job.status == JobStatus.CLOSED,
            )
            .count()
        )

        jobs_today = (
            db.query(Assignment)
            .filter(Assignment.technician_id == tech.id, Assignment.assigned_at >= today_start)
            .count()
        )

        estimated_minutes = round((distance_km / AVERAGE_SPEED_KMH) * 60)

        results.append(
            {
                "technician_id": tech.id,
                "name": tech.user.name,
                "distance_km": round(distance_km, 1),
                "experience_count": experience_count,
                "jobs_today": jobs_today,
                "estimated_minutes": estimated_minutes,
            }
        )

    max_distance = max((r["distance_km"] for r in results), default=1) or 1
    max_experience = max((r["experience_count"] for r in results), default=1) or 1
    max_jobs_today = max((r["jobs_today"] for r in results), default=1) or 1

    for r in results:
        distance_score = 1 - (r["distance_km"] / max_distance)
        experience_score = r["experience_count"] / max_experience
        workload_score = 1 - (r["jobs_today"] / max_jobs_today) if max_jobs_today else 1

        composite = (distance_score * 0.4) + (experience_score * 0.35) + (workload_score * 0.25)
        r["confidence_percent"] = round(composite * 100)

    results.sort(key=lambda r: r["confidence_percent"], reverse=True)
    return results