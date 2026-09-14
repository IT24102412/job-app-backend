from datetime import datetime, time, date
from calendar import monthrange

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Assignment, Job, JobStatus, RegionalCenter, Technician
from app.services.assignment_service import calculate_job_summary


def get_monthly_report(year: int, month: int, db: Session) -> dict:
    start_date = datetime(year, month, 1)
    last_day = monthrange(year, month)[1]
    end_date = datetime(year, month, last_day, 23, 59, 59)

    jobs = db.query(Job).filter(Job.created_at >= start_date, Job.created_at <= end_date).all()

    total_jobs = len(jobs)

    by_status = {}
    for j in jobs:
        by_status[j.status.value] = by_status.get(j.status.value, 0) + 1

    by_service_type = {}
    for j in jobs:
        by_service_type[j.service_type.value] = by_service_type.get(j.service_type.value, 0) + 1

    by_regional_center = {}
    for j in jobs:
        if j.regional_center_id:
            center = db.query(RegionalCenter).filter(RegionalCenter.id == j.regional_center_id).first()
            name = center.name if center else f"Center {j.regional_center_id}"
            by_regional_center[name] = by_regional_center.get(name, 0) + 1

    closed_jobs = [j for j in jobs if j.status == JobStatus.CLOSED and j.closed_at]
    if closed_jobs:
        total_hours = sum((j.closed_at - j.created_at).total_seconds() / 3600 for j in closed_jobs)
        avg_hours_to_close = round(total_hours / len(closed_jobs), 1)
    else:
        avg_hours_to_close = None

    return {
        "year": year,
        "month": month,
        "total_jobs": total_jobs,
        "by_status": by_status,
        "by_service_type": by_service_type,
        "by_regional_center": by_regional_center,
        "average_hours_to_close": avg_hours_to_close,
    }


def get_daily_technician_report(report_date: date, db: Session) -> list[dict]:
    """For a given day, returns each technician's completed jobs, total time, and total distance."""
    start = datetime.combine(report_date, time.min)
    end = datetime.combine(report_date, time.max)

    closed_jobs = (
        db.query(Job)
        .filter(Job.status == JobStatus.CLOSED, Job.closed_at >= start, Job.closed_at <= end)
        .all()
    )

    entries_by_tech: dict = {}

    for job in closed_jobs:
        assignment = (
            db.query(Assignment)
            .filter(Assignment.job_id == job.id, Assignment.status == "completed")
            .order_by(Assignment.assigned_at.desc())
            .first()
        )

        if assignment:
            technician = db.query(Technician).filter(Technician.id == assignment.technician_id).first()
            tech_key = technician.id if technician else "unassigned"
            tech_name = technician.user.name if technician else "Unassigned"
            region = None
            if technician:
                region = db.query(RegionalCenter).filter(RegionalCenter.id == technician.regional_center_id).first()
            region_name = region.name if region else None
        else:
            tech_key = "unassigned"
            tech_name = "Unassigned"
            region_name = None

        summary = calculate_job_summary(job, db)

        if tech_key not in entries_by_tech:
            entries_by_tech[tech_key] = {
                "technician_name": tech_name,
                "regional_center": region_name,
                "jobs_closed": 0,
                "job_numbers": [],
                "total_hours": 0.0,
                "total_km": 0.0,
            }

        entry = entries_by_tech[tech_key]
        entry["jobs_closed"] += 1
        entry["job_numbers"].append(job.job_number)
        if summary["duration_hours"] is not None:
            entry["total_hours"] += summary["duration_hours"]
        if summary["total_distance_km"] is not None:
            entry["total_km"] += summary["total_distance_km"]

    results = list(entries_by_tech.values())
    for entry in results:
        entry["total_hours"] = round(entry["total_hours"], 2)
        entry["total_km"] = round(entry["total_km"], 2)

    results.sort(key=lambda e: e["jobs_closed"], reverse=True)
    return results