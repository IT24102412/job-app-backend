import random
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import create_access_token, verify_password
from app.database import get_db
from app.models import PasswordResetOTP, User
from app.schemas import Token
from app.services.sms_service import send_otp_sms

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

OTP_VALID_MINUTES = 10


class ForgotPasswordRequest(BaseModel):
    phone: str


class ResetPasswordWithOTPRequest(BaseModel):
    phone: str
    otp_code: str
    new_password: str = Field(min_length=8)


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect phone or password")

    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value, "name": user.name}
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == payload.phone).first()

    # Always return the same generic message, whether or not this phone exists —
    # this avoids letting someone probe which phone numbers are registered.
    generic_response = {"detail": "If this phone number is registered, a verification code has been sent."}

    if not user:
        return generic_response

    otp_code = f"{random.randint(0, 999999):06d}"
    otp = PasswordResetOTP(
        phone=payload.phone,
        otp_code=otp_code,
        expires_at=datetime.utcnow() + timedelta(minutes=OTP_VALID_MINUTES),
    )
    db.add(otp)
    db.commit()

    send_otp_sms(payload.phone, otp_code)

    return generic_response


@router.post("/reset-password")
def reset_password(payload: ResetPasswordWithOTPRequest, db: Session = Depends(get_db)):
    otp = (
        db.query(PasswordResetOTP)
        .filter(
            PasswordResetOTP.phone == payload.phone,
            PasswordResetOTP.otp_code == payload.otp_code,
            PasswordResetOTP.used == False,
            PasswordResetOTP.expires_at > datetime.utcnow(),
        )
        .order_by(PasswordResetOTP.created_at.desc())
        .first()
    )

    if not otp:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    user = db.query(User).filter(User.phone == payload.phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = pwd_context.hash(payload.new_password)
    otp.used = True
    db.commit()

    return {"detail": "Password reset successfully. You can now log in with your new password."}