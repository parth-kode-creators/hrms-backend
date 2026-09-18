from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import date, datetime


class LeaveTypeItem(BaseModel):
    id: int
    name: str
    default_days_per_year: int
    is_paid: bool

    model_config = ConfigDict(from_attributes=True)


class LeaveTypeListResponse(BaseModel):
    items: List[LeaveTypeItem]


class LeaveTypeCreate(BaseModel):
    name: str
    default_days_per_year: int = 0
    is_paid: bool = True
    carry_forward: bool = False


class LeaveBalanceItem(BaseModel):
    leave_type: str
    total_allotted: float
    used: float
    balance: float


class LeaveBalanceMeResponse(BaseModel):
    items: List[LeaveBalanceItem]


class LeaveApplyRequest(BaseModel):
    leave_type_id: int
    start_date: date
    end_date: date
    is_half_day: bool = False
    reason: Optional[str] = None


class LeaveApplyResponse(BaseModel):
    id: int
    status: str
    applied_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LeaveRejectRequest(BaseModel):
    comment: Optional[str] = None


class LeaveDecisionResponse(BaseModel):
    id: int
    status: str
    decided_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class LeaveRequestItem(BaseModel):
    id: int
    employee_id: int
    employee_name: Optional[str] = None
    leave_type: str
    start_date: date
    end_date: date
    is_half_day: bool
    reason: Optional[str] = None
    status: str
    applied_at: datetime
    decided_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class LeaveRequestListResponse(BaseModel):
    items: List[LeaveRequestItem]
