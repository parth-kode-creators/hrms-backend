from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import date, datetime
from app.models.enums import CheckMethod


class CheckInRequest(BaseModel):
    lat: Optional[float] = None
    lng: Optional[float] = None
    method: CheckMethod = CheckMethod.mobile_geofence


class CheckInResponse(BaseModel):
    id: int
    employee_id: int
    date: date
    check_in_time: datetime
    status: str

    model_config = ConfigDict(from_attributes=True)


class CheckOutRequest(BaseModel):
    lat: Optional[float] = None
    lng: Optional[float] = None
    method: CheckMethod = CheckMethod.mobile_geofence


class CheckOutResponse(BaseModel):
    id: int
    check_out_time: datetime
    total_hours: float

    model_config = ConfigDict(from_attributes=True)


class AttendanceLogItem(BaseModel):
    date: str
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    total_hours: Optional[float] = None
    status: str

    model_config = ConfigDict(from_attributes=True)


class AttendanceMeResponse(BaseModel):
    items: List[AttendanceLogItem]


class AttendanceHistoryItem(BaseModel):
    id: int
    employee_id: int
    employee_name: Optional[str] = None
    employee_code: Optional[str] = None
    department: Optional[str] = None
    date: date
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    check_in_method: Optional[CheckMethod] = None
    check_out_method: Optional[CheckMethod] = None
    check_in_ip: Optional[str] = None
    check_in_lat: Optional[float] = None
    check_in_lng: Optional[float] = None
    status: str
    is_regularized: bool = False
    regularize_reason: Optional[str] = None
    total_hours: Optional[float] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AttendanceHistoryResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[AttendanceHistoryItem]


class RegularizeRequest(BaseModel):
    attendance_id: int
    requested_check_in: Optional[datetime] = None
    requested_check_out: Optional[datetime] = None
    reason: Optional[str] = None


class RegularizeResponse(BaseModel):
    id: int
    status: str

    model_config = ConfigDict(from_attributes=True)


class ApproveRegularizeRequest(BaseModel):
    approve: bool


class WFHRequest(BaseModel):
    date: date
    reason: Optional[str] = None


class WFHResponse(BaseModel):
    id: int
    status: str

    model_config = ConfigDict(from_attributes=True)


class ImportErrorItem(BaseModel):
    row: int
    reason: str


class ImportResponse(BaseModel):
    imported: int
    skipped: int
    errors: List[ImportErrorItem]
