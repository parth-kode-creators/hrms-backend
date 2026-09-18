from pydantic import BaseModel
from typing import List


class LeaveTrendMonth(BaseModel):
    month: str
    count: int


class DashboardReportResponse(BaseModel):
    headcount: int
    today_attendance_pct: float
    pending_leave_approvals: int
    active_projects: int
    leave_trend_last_6_months: List[LeaveTrendMonth]
