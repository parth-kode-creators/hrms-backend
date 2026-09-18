from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict
from datetime import date


class CalendarEventItem(BaseModel):
    employee_id: Optional[int] = None
    name: str
    type: str  # "leave" or "holiday"
    leave_type: Optional[str] = None
    half_day: Optional[bool] = None
    holiday_name: Optional[str] = None


class TeamCalendarResponse(BaseModel):
    days: Dict[str, List[CalendarEventItem]]


class DayDetailEmployee(BaseModel):
    id: int
    full_name: str

    model_config = ConfigDict(from_attributes=True)


class DayDetailLeave(BaseModel):
    type: str
    half_day: bool
    status: str


class DayDetailAttendance(BaseModel):
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    total_hours: Optional[float] = None


class DayDetailTaskLog(BaseModel):
    task_title: str
    hours_spent: float
    notes: Optional[str] = None


class DayDetailResponse(BaseModel):
    employee: DayDetailEmployee
    leave: Optional[DayDetailLeave] = None
    attendance: Optional[DayDetailAttendance] = None
    task_logs: List[DayDetailTaskLog] = []
