from datetime import datetime, date, timedelta, timezone
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_, extract

from app.db.session import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.employee import Employee
from app.models.attendance import Attendance
from app.models.leave import LeaveRequest
from app.models.project import Project, ProjectMember
from app.models.enums import UserRole
from app.schemas.report import DashboardReportResponse, LeaveTrendMonth

router = APIRouter()


@router.get("/dashboard", response_model=DashboardReportResponse, summary="Get dashboard metrics")
def get_dashboard_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve real-time KPI metrics tailored to the caller's role (Admin, Manager, Employee).
    """
    today = datetime.now(timezone.utc).date()
    is_admin = current_user.role in [UserRole.super_admin, UserRole.hr_admin]
    is_manager = current_user.role == UserRole.manager
    user_emp_id = current_user.employee_id

    # 1. Headcount
    if is_admin:
        headcount = db.execute(select(func.count(Employee.id)).where(Employee.status == "active")).scalar() or 0
    elif is_manager:
        headcount = db.execute(
            select(func.count(Employee.id)).where(
                Employee.status == "active",
                or_(Employee.id == user_emp_id, Employee.manager_id == user_emp_id)
            )
        ).scalar() or 0
    else:
        headcount = 1

    # 2. Today's Attendance Percentage
    if is_admin:
        attended_today = db.execute(
            select(func.count(Attendance.id)).where(
                Attendance.date == today,
                Attendance.check_in_time.is_not(None)
            )
        ).scalar() or 0
        today_attendance_pct = round((attended_today / headcount * 100.0), 1) if headcount > 0 else 0.0
    elif is_manager:
        attended_today = db.execute(
            select(func.count(Attendance.id))
            .join(Employee, Attendance.employee_id == Employee.id)
            .where(
                Attendance.date == today,
                Attendance.check_in_time.is_not(None),
                or_(Employee.id == user_emp_id, Employee.manager_id == user_emp_id)
            )
        ).scalar() or 0
        today_attendance_pct = round((attended_today / headcount * 100.0), 1) if headcount > 0 else 0.0
    else:
        self_attended = db.execute(
            select(Attendance).where(
                Attendance.employee_id == user_emp_id,
                Attendance.date == today,
                Attendance.check_in_time.is_not(None)
            )
        ).scalar_one_or_none()
        today_attendance_pct = 100.0 if self_attended else 0.0

    # 3. Pending Leave Approvals
    if is_admin:
        pending_leaves = db.execute(
            select(func.count(LeaveRequest.id)).where(LeaveRequest.status == "pending")
        ).scalar() or 0
    elif is_manager:
        pending_leaves = db.execute(
            select(func.count(LeaveRequest.id))
            .join(Employee, LeaveRequest.employee_id == Employee.id)
            .where(
                LeaveRequest.status == "pending",
                Employee.manager_id == user_emp_id
            )
        ).scalar() or 0
    else:
        pending_leaves = db.execute(
            select(func.count(LeaveRequest.id)).where(
                LeaveRequest.status == "pending",
                LeaveRequest.employee_id == user_emp_id
            )
        ).scalar() or 0

    # 4. Active Projects
    if is_admin:
        active_projects = db.execute(
            select(func.count(Project.id)).where(Project.status == "active")
        ).scalar() or 0
    else:
        member_proj_ids = select(ProjectMember.project_id).where(
            ProjectMember.employee_id == user_emp_id
        )
        active_projects = db.execute(
            select(func.count(Project.id)).where(
                Project.status == "active",
                or_(
                    Project.created_by == user_emp_id,
                    Project.id.in_(member_proj_ids)
                )
            )
        ).scalar() or 0

    # 5. Leave Trend (Last 6 Months)
    # Generate list of past 6 months
    leave_trends: List[LeaveTrendMonth] = []
    current_dt = datetime.now(timezone.utc)
    for i in range(5, -1, -1):
        # Calculate month offset
        year = current_dt.year
        month = current_dt.month - i
        while month <= 0:
            month += 12
            year -= 1

        month_label = datetime(year, month, 1).strftime("%b")

        stmt = select(func.count(LeaveRequest.id)).where(
            extract("year", LeaveRequest.start_date) == year,
            extract("month", LeaveRequest.start_date) == month,
            LeaveRequest.status == "approved"
        )
        if not is_admin:
            if is_manager:
                stmt = stmt.join(Employee, LeaveRequest.employee_id == Employee.id).where(
                    or_(Employee.id == user_emp_id, Employee.manager_id == user_emp_id)
                )
            else:
                stmt = stmt.where(LeaveRequest.employee_id == user_emp_id)

        count = db.execute(stmt).scalar() or 0
        leave_trends.append(LeaveTrendMonth(month=month_label, count=count))

    return DashboardReportResponse(
        headcount=headcount,
        today_attendance_pct=today_attendance_pct,
        pending_leave_approvals=pending_leaves,
        active_projects=active_projects,
        leave_trend_last_6_months=leave_trends
    )
