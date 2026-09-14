from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import Notification, Technician, User, UserRole
from app.schemas import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/me", response_model=list[NotificationOut])
def get_my_notifications(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role == UserRole.ADMIN:
        return (
            db.query(Notification)
            .filter(Notification.recipient_admin_id == current_user.id)
            .order_by(Notification.created_at.desc())
            .all()
        )

    technician = db.query(Technician).filter(Technician.user_id == current_user.id).first()
    if not technician:
        return []

    return (
        db.query(Notification)
        .filter(Notification.technician_id == technician.id)
        .order_by(Notification.created_at.desc())
        .all()
    )


@router.get("/recent-activity", response_model=list[NotificationOut])
def get_recent_activity(
    limit: int = 15,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN)),
):
    return (
        db.query(Notification)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/technician/{technician_id}", response_model=list[NotificationOut])
def get_technician_notifications(
    technician_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    technician = db.query(Technician).filter(Technician.id == technician_id).first()
    if not technician:
        raise HTTPException(status_code=404, detail="Technician not found")

    if technician.user_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="You can only view your own notifications")

    return (
        db.query(Notification)
        .filter(Notification.technician_id == technician_id)
        .order_by(Notification.created_at.desc())
        .all()
    )


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_as_read(
    notification_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    if notification.recipient_admin_id is not None:
        if notification.recipient_admin_id != current_user.id:
            raise HTTPException(status_code=403, detail="You can only mark your own notifications as read")
    else:
        technician = db.query(Technician).filter(Technician.id == notification.technician_id).first()
        if technician.user_id != current_user.id and current_user.role.value != "admin":
            raise HTTPException(status_code=403, detail="You can only mark your own notifications as read")

    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification