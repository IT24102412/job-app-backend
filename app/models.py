from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    SALES_EXECUTIVE = "sales_executive"
    TECHNICIAN = "technician"
    ADMIN = "admin"


class JobType(str, enum.Enum):
    WORKSHOP = "workshop"
    REGIONAL = "regional"


class ServiceType(str, enum.Enum):
    BREAKDOWN = "breakdown"
    SERVICE = "service"
    INSPECTION = "inspection"


class JobStatus(str, enum.Enum):
    CREATED = "created"
    ASSIGNED = "assigned"
    STARTED = "started"
    SHEET_UPLOADED = "sheet_uploaded"
    CLOSED = "closed"
    CANCELLED = "cancelled"


def _text_enum(enum_cls):
    """Stores enums as plain text (VARCHAR) instead of a native database enum type.
    This matters specifically on PostgreSQL, which enforces strict native enum types
    that require a slow ALTER TYPE migration every time a value is added or changed.
    SQL Server never had this issue since it doesn't have native enums, but we want
    the same easy, low-friction schema changes on Postgres going forward."""
    return Enum(enum_cls, values_callable=lambda x: [e.value for e in x], native_enum=False)


class RegionalCenter(Base):
    __tablename__ = "regional_centers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    technicians: Mapped[list["Technician"]] = relationship(back_populates="regional_center")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    email: Mapped[str | None] = mapped_column(String(120), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(_text_enum(UserRole), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    technician_profile: Mapped["Technician | None"] = relationship(back_populates="user", uselist=False)
    jobs_created: Mapped[list["Job"]] = relationship(back_populates="sales_executive")


class Technician(Base):
    __tablename__ = "technicians"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True)
    regional_center_id: Mapped[int] = mapped_column(ForeignKey("regional_centers.id"), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship(back_populates="technician_profile")
    regional_center: Mapped["RegionalCenter"] = relationship(back_populates="technicians")
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="technician")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="technician")


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    address: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    jobs: Mapped[list["Job"]] = relationship(back_populates="customer")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    job_type: Mapped[JobType] = mapped_column(_text_enum(JobType), nullable=False)
    service_type: Mapped[ServiceType] = mapped_column(_text_enum(ServiceType), nullable=False)
    remarks: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[JobStatus] = mapped_column(_text_enum(JobStatus), default=JobStatus.CREATED)

    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    sales_executive_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    regional_center_id: Mapped[int | None] = mapped_column(ForeignKey("regional_centers.id"))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    closed_reason: Mapped[str | None] = mapped_column(String(500))
    closed_by_admin: Mapped[bool] = mapped_column(Boolean, default=False)

    customer: Mapped["Customer"] = relationship(back_populates="jobs")
    sales_executive: Mapped["User"] = relationship(back_populates="jobs_created")
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="job")
    locations: Mapped[list["Location"]] = relationship(back_populates="job")
    jobsheets: Mapped[list["Jobsheet"]] = relationship(back_populates="job")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="job")


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    technician_id: Mapped[int] = mapped_column(ForeignKey("technicians.id"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    unassigned_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="active")

    job: Mapped["Job"] = relationship(back_populates="assignments")
    technician: Mapped["Technician"] = relationship(back_populates="assignments")


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    technician_id: Mapped[int] = mapped_column(ForeignKey("technicians.id"), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job: Mapped["Job"] = relationship(back_populates="locations")


class Jobsheet(Base):
    __tablename__ = "jobsheets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job: Mapped["Job"] = relationship(back_populates="jobsheets")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    technician_id: Mapped[int | None] = mapped_column(ForeignKey("technicians.id"))
    recipient_admin_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    message: Mapped[str] = mapped_column(String(255), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job: Mapped["Job"] = relationship(back_populates="notifications")
    technician: Mapped["Technician | None"] = relationship(back_populates="notifications")