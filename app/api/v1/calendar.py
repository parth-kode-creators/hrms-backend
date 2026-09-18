from datetime import datetime, date, timedelta, timezone
from typing import Optional, Dict, List
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, or_, extract

from app.db.session import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.employee import Employee
from app.models.holiday import Holiday
from app.models.leave import LeaveRequest
from app.models.attendance import Attendance
from app.models.task import TaskLog, Task
from app.models.enums import UserRole
from app.schemas.calendar import (
    TeamCalendarResponse,
    CalendarEventItem,
    DayDetailResponse,
    DayDetailEmployee,
    DayDetailLeave,
    DayDetailAttendance,
    DayDetailTaskLog,
)

router = APIRouter()


@router.get("/team", response_model=TeamCalendarResponse, summary="Get merged team calendar")
def get_team_calendar(
    month: Optional[int] = Query(None, ge=1, le=12, description="Month (1-12)"),
    year: Optional[int] = Query(None, description="Year (e.g. 2026)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get merged calendar view showing company holidays and approved leaves for the user's team.
    """
    now = datetime.now(timezone.utc)
    target_month = month or now.month
    target_year = year or now.year

    events_by_day = defaultdict(list)

    # 1. Fetch holidays for the month/year
    holidays = db.execute(
        select(Holiday).where(
            Holiday.year == target_year,
            extract("month", Holiday.date) == target_month
        )
    ).scalars().all()

    for h in holidays:
        day_key = h.date.strftime("%Y-%m-%d")
        events_by_day[day_key].append(
            CalendarEventItem(
                employee_id=None,
                name="Company Holiday",
                type="holiday",
                holiday_name=h.name
            )
        )

    # 2. Fetch approved leaves for the month/year scoped by role
    leave_stmt = (
        select(LeaveRequest)
        .options(
            joinedload(LeaveRequest.employee),
            joinedload(LeaveRequest.leave_type)
        )
        .where(
            LeaveRequest.status == "approved",
            extract("year", LeaveRequest.start_date) <= target_year,
            extract("year", LeaveRequest.end_date) >= target_year
        )
    )

    if current_user.role in [UserRole.super_admin, UserRole.hr_admin]:
        pass  # Global visibility
    elif current_user.role == UserRole.manager:
        leave_stmt = leave_stmt.join(Employee, LeaveRequest.employee_id == Employee.id).where(
            or_(
                Employee.id == current_user.employee_id,
                Employee.manager_id == current_user.employee_id
            )
        )
    else:
        # If user belongs to department, see department approved leaves; otherwise self
        if current_user.employee and current_user.employee.department_id:
            leave_stmt = leave_stmt.join(Employee, LeaveRequest.employee_id == Employee.id).where(
                or_(
                    Employee.department_id == current_user.employee.department_id,
                    Employee.id == current_user.employee_id
                )
            )
        else:
            leave_stmt = leave_stmt.where(LeaveRequest.employee_id == current_user.employee_id)

    approved_leaves = db.execute(leave_stmt).scalars().all()

    for lr in approved_leaves:
        curr_d = lr.start_date
        while curr_d <= lr.end_date:
            if curr_d.month == target_month and curr_d.year == target_year:
                day_key = curr_d.strftime("%Y-%m-%d")
                events_by_day[day_key].append(
                    CalendarEventItem(
                        employee_id=lr.employee_id,
                        name=lr.employee.full_name if lr.employee else "Employee",
                        type="leave",
                        leave_type=lr.leave_type.name if lr.leave_type else "Leave",
                        half_day=lr.is_half_day
                    )
                )
            curr_d += timedelta(days=1)

    return TeamCalendarResponse(days=dict(sorted(events_by_day.items())))


@router.get("/day/{employee_id}/{date_str}", response_model=DayDetailResponse, summary="Get employee daily summary")
def get_employee_day_detail(
    employee_id: int,
    date_str: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed timeline of an employee for a specific day:
    combines approved leave, attendance check-in/out, and logged task hours.
    """
    # Parse target date
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format, expected YYYY-MM-DD")

    # Fetch employee
    employee = db.execute(select(Employee).where(Employee.id == employee_id)).scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    # Scoping check
    if current_user.role in [UserRole.super_admin, UserRole.hr_admin]:
        pass
    elif current_user.role == UserRole.manager:
        if employee.id != current_user.employee_id and employee.manager_id != current_user.employee_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this employee's schedule")
    else:
        if employee.id != current_user.employee_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # 1. Check approved leave on target date
    leave_record = db.execute(
        select(LeaveRequest)
        .options(joinedload(LeaveRequest.leave_type))
        .where(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status == "approved",
            LeaveRequest.start_date <= target_date,
            LeaveRequest.end_date >= target_date
        )
    ).scalar_one_or_none()

    leave_detail = None
    if leave_record:
        leave_detail = DayDetailLeave(
            type=leave_record.leave_type.name if leave_record.leave_type else "Leave",
            half_day=leave_record.is_half_day,
            status=leave_record.status
        )

    # 2. Check attendance record on target date
    att_record = db.execute(
        select(Attendance).where(
            Attendance.employee_id == employee_id,
            Attendance.date == target_date
        )
    ).scalar_one_or_none()

    att_detail = None
    if att_record:
        att_detail = DayDetailAttendance(
            check_in=att_record.check_in_time.strftime("%H:%M") if att_record.check_in_time else None,
            check_out=att_record.check_out_time.strftime("%H:%M") if att_record.check_out_time else None,
            total_hours=float(att_record.total_hours) if att_record.total_hours is not None else None
        )

    # 3. Check task logs for target date
    task_logs = db.execute(
        select(TaskLog)
        .options(joinedload(TaskLog.task))
        .where(
            TaskLog.employee_id == employee_id,
            TaskLog.log_date == target_date
        )
    ).scalars().all()

    logs_detail = [
        DayDetailTaskLog(
            task_title=l.task.title if l.task else "Untitled Task",
            hours_spent=float(l.hours_spent),
            notes=l.notes
        )
        for l in task_logs
    ]

    return DayDetailResponse(
        employee=DayDetailEmployee(id=employee.id, full_name=employee.full_name),
        leave=leave_detail,
        attendance=att_detail,
        task_logs=logs_detail
    )
