from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List
from datetime import date, datetime
from app.models.enums import UserRole
from app.schemas.department import DepartmentSimple
from app.schemas.office_location import OfficeLocationSimple


class ManagerSimple(BaseModel):
    id: int
    full_name: str

    model_config = ConfigDict(from_attributes=True)


class EmployeeCreate(BaseModel):
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    department_id: Optional[int] = None
    designation: Optional[str] = None
    date_of_joining: Optional[date] = None
    manager_id: Optional[int] = None
    office_location_id: Optional[int] = None
    status: Optional[str] = "active"
    role: Optional[UserRole] = UserRole.employee
    password: Optional[str] = "DefaultPassword123!"


class EmployeeUpdate(BaseModel):
    # Fields that employees themselves can update
    phone: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    profile_photo_url: Optional[str] = None

    # Fields that only HR/Super Admin can update
    full_name: Optional[str] = None
    department_id: Optional[int] = None
    designation: Optional[str] = None
    date_of_joining: Optional[date] = None
    manager_id: Optional[int] = None
    office_location_id: Optional[int] = None
    status: Optional[str] = None


class EmployeeListItem(BaseModel):
    id: int
    full_name: str
    designation: Optional[str] = None
    department: Optional[str] = None
    status: str

    model_config = ConfigDict(from_attributes=True)


class EmployeeListResponse(BaseModel):
    total: int
    page: int
    items: List[EmployeeListItem]


class EmployeeDetail(BaseModel):
    id: int
    employee_code: str
    full_name: str
    email: str
    phone: Optional[str] = None
    department: Optional[DepartmentSimple] = None
    designation: Optional[str] = None
    manager: Optional[ManagerSimple] = None
    office_location: Optional[OfficeLocationSimple] = None
    date_of_joining: Optional[date] = None
    status: str
    profile_photo_url: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ResetPasswordRequest(BaseModel):
    new_password: str

