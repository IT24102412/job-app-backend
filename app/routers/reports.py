from datetime import date, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_role
from app.models import UserRole
from app.schemas import DailyTechnicianReportOut, MonthlyReportOut
from app.services.report_service import get_daily_technician_report, get_monthly_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/monthly", response_model=MonthlyReportOut)
def monthly_report(
    year: int = None,
    month: int = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN)),
):
    now = datetime.utcnow()
    year = year or now.year
    month = month or now.month
    return get_monthly_report(year, month, db)


@router.get("/daily-technicians", response_model=list[DailyTechnicianReportOut])
def daily_technician_report(
    report_date: date = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN)),
):
    report_date = report_date or date.today()
    return get_daily_technician_report(report_date, db)