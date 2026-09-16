from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models import JobStatus, JobType, RequestType, ServiceType, UserRole


def _validate_phone(value: str) -> str:
    if not value.isdigit() or len(value) != 10:
        raise ValueError("Phone number must be exactly 10 digits")
    return value


class UserCreate(BaseModel):
    name: str = Field(min_length=2)
    phone: str
    email: EmailStr | None = None
    password: str = Field(min_length=8)
    role: UserRole

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        return _validate_phone(value)


class UserOut(BaseModel):
    id: int
    name: str
    phone: str
    email: str | None
    role: UserRole

    class Config:
        from_attributes = True


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8)


class CustomerCreate(BaseModel):
    name: str = Field(min_length=2)
    phone: str | None = None
    address: str | None = Field(default=None, min_length=5)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _validate_phone(value)


class CustomerOut(BaseModel):
    id: int
    name: str
    phone: str | None
    address: str | None
    latitude: float
    longitude: float

    class Config:
        from_attributes = True


class JobCreate(BaseModel):
    request_type: RequestType
    job_type: JobType
    service_type: ServiceType
    remarks: str | None = Field(default=None, max_length=500)
    customer_id: int = Field(gt=0)
    sales_executive_id: int = Field(gt=0)
    regional_center_id: int | None = Field(default=None, gt=0)


class JobOut(BaseModel):
    id: int
    job_number: str
    request_type: RequestType
    job_type: JobType
    service_type: ServiceType
    remarks: str | None
    status: JobStatus
    customer_id: int
    customer_name: str | None
    sales_executive_id: int
    regional_center_id: int | None
    created_at: datetime
    started_at: datetime | None
    closed_at: datetime | None
    closed_reason: str | None
    closed_by_admin: bool
    has_sr_attachment: bool

    class Config:
        from_attributes = True


class JobSummaryOut(BaseModel):
    duration_hours: float | None
    total_distance_km: float | None


class AssignedTechnicianOut(BaseModel):
    id: int
    user_id: int
    name: str
    regional_center_name: str | None
    status: str
    started_at: datetime | None


class AdminCloseJobRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class RegionalCenterCreate(BaseModel):
    name: str = Field(min_length=2)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class RegionalCenterOut(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float

    class Config:
        from_attributes = True


class TechnicianCreate(BaseModel):
    user_id: int = Field(gt=0)
    regional_center_id: int = Field(gt=0)
    is_available: bool = True


class TechnicianOut(BaseModel):
    id: int
    user_id: int
    regional_center_id: int
    is_available: bool

    class Config:
        from_attributes = True


class TechnicianWithNameOut(BaseModel):
    id: int
    user_id: int
    regional_center_id: int
    is_available: bool
    name: str
    regional_center_name: str | None = None

    class Config:
        from_attributes = True


class TechnicianRecommendationOut(BaseModel):
    technician_id: int
    name: str
    distance_km: float
    experience_count: int
    jobs_today: int
    estimated_minutes: int
    confidence_percent: int


class AssignmentOut(BaseModel):
    id: int
    job_id: int
    technician_id: int
    assigned_at: datetime
    started_at: datetime | None
    status: str

    class Config:
        from_attributes = True


class NotificationOut(BaseModel):
    id: int
    job_id: int
    technician_id: int | None
    recipient_admin_id: int | None
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class JobsheetOut(BaseModel):
    id: int
    job_id: int
    file_url: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


class LocationCreate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class LocationOut(BaseModel):
    id: int
    job_id: int
    technician_id: int
    latitude: float
    longitude: float
    recorded_at: datetime

    class Config:
        from_attributes = True


class MonthlyReportOut(BaseModel):
    year: int
    month: int
    total_jobs: int
    by_status: dict[str, int]
    by_service_type: dict[str, int]
    by_regional_center: dict[str, int]
    average_hours_to_close: float | None


class DailyTechnicianReportOut(BaseModel):
    technician_name: str
    regional_center: str | None
    jobs_closed: int
    job_numbers: list[str]
    total_hours: float
    total_km: float