from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth import create_access_token, verify_password
from app.database import get_db
from app.models import User
from app.schemas import Token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect phone or password")

    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value, "name": user.name}
    )
    return {"access_token": access_token, "token_type": "bearer"}