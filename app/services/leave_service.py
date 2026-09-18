from datetime import date, datetime, timedelta, timezone
from typing import List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_
from fastapi import HTTPException, status

from app.models.leave import LeaveType, LeaveBalance, LeaveRequest
from app.models.holiday import Holiday
from app.models.enums import HolidayType, LeaveRequestStatus
from app.models.notification import Notification


def calculate_requested_leave_days(
    db: Session,
    start_date: date,
    end_date: date,
    is_half_day: bool
) -> float:
    """
    Calculate working days between start_date and end_date (inclusive),
    excluding weekends (Saturday=5, Sunday=6) and mandatory company holidays.
    If is_half_day is True, returns 0.5.
    """
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date cannot be after end_date"
        )

    if is_half_day:
        if start_date != end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Half-day leave must have start_date equal to end_date"
            )
        return 0.5

    # Fetch mandatory holidays in this date range
    holidays = db.execute(
        select(Holiday.date).where(
            Holiday.date >= start_date,
            Holiday.date <= end_date,
            Holiday.type.in_([HolidayType.mandatory, HolidayType.festival])
        )
    ).scalars().all()
    holiday_set = set(holidays)

    current = start_date
    working_days = 0.0
    while current <= end_date:
        # Check if weekend (Saturday=5, Sunday=6) or mandatory holiday
        if current.weekday() < 5 and current not in holiday_set:
            working_days += 1.0
        current += timedelta(days=1)

    if working_days == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selected dates contain only weekends or public holidays"
        )

    return working_days


def check_leave_balance(
    db: Session,
    employee_id: int,
    leave_type_id: int,
    year: int,
    requested_days: float
) -> Tuple[LeaveBalance, LeaveType]:
    """
    Verify that the employee has sufficient balance for the requested leave type.
    """
    leave_type = db.execute(select(LeaveType).where(LeaveType.id == leave_type_id)).scalar_one_or_none()
    if not leave_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave type not found")

    balance = db.execute(
        select(LeaveBalance).where(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.leave_type_id == leave_type_id,
            LeaveBalance.year == year
        )
    ).scalar_one_or_none()

    if not balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No {leave_type.name} leave balance allocated for year {year}"
        )

    avail = float(balance.balance)
    if avail < requested_days:
        avail_str = int(avail) if avail.is_integer() else avail
        req_str = int(requested_days) if requested_days.is_integer() else requested_days
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient {leave_type.name} leave balance. Available: {avail_str}, Requested: {req_str}"
        )

    return balance, leave_type


def check_overlapping_leaves(
    db: Session,
    employee_id: int,
    start_date: date,
    end_date: date,
    exclude_request_id: int = None
) -> None:
    """
    Check if employee has an existing pending or approved leave overlapping with the requested dates.
    """
    query = select(LeaveRequest).where(
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.status.in_(["pending", "approved"]),
        LeaveRequest.start_date <= end_date,
        LeaveRequest.end_date >= start_date
    )
    if exclude_request_id:
        query = query.where(LeaveRequest.id != exclude_request_id)

    overlap = db.execute(query).scalar_one_or_none()
    if overlap:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Leave request overlaps with an existing {overlap.status} leave ({overlap.start_date} to {overlap.end_date})"
        )


def deduct_leave_balance(
    db: Session,
    leave_request: LeaveRequest,
    approver_id: int
) -> None:
    """
    Atomically deduct approved leave days from employee's balance and record decision.
    """
    requested_days = calculate_requested_leave_days(
        db, leave_request.start_date, leave_request.end_date, leave_request.is_half_day
    )
    year = leave_request.start_date.year

    balance, leave_type = check_leave_balance(
        db, leave_request.employee_id, leave_request.leave_type_id, year, requested_days
    )

    balance.used = float(balance.used) + requested_days
    balance.balance = float(balance.balance) - requested_days

    leave_request.status = "approved"
    leave_request.approved_by = approver_id
    leave_request.decided_at = datetime.now(timezone.utc)

    # In-app notification
    notification = Notification(
        employee_id=leave_request.employee_id,
        title="Leave Approved",
        body=f"Your {leave_type.name} leave for {leave_request.start_date} to {leave_request.end_date} has been approved.",
        type="leave_approved"
    )
    db.add(notification)
