from fastapi import APIRouter, Depends, HTTPException
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import User, UserRole
from app.schemas import AdminResetPasswordRequest, ChangePasswordRequest, UserCreate, UserOut

router = APIRouter(prefix="/users", tags=["users"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/", response_model=UserOut)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    user = User(
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        password_hash=pwd_context.hash(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), current_user=Depends(require_role(UserRole.ADMIN))):
    return db.query(User).all()


@router.post("/me/change-password")
def change_my_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not pwd_context.verify(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    current_user.password_hash = pwd_context.hash(payload.new_password)
    db.commit()
    return {"detail": "Password changed successfully"}


@router.post("/{user_id}/reset-password")
def admin_reset_password(
    user_id: int,
    payload: AdminResetPasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = pwd_context.hash(payload.new_password)
    db.commit()
    return {"detail": f"Password reset for {user.name}"}