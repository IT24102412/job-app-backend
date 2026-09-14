from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import Customer, UserRole
from app.schemas import CustomerCreate, CustomerOut

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("/", response_model=CustomerOut)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.SALES_EXECUTIVE, UserRole.ADMIN)),
):
    customer = Customer(**payload.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("/", response_model=list[CustomerOut])
def list_customers(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return db.query(Customer).all()


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer