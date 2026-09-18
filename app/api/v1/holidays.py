from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.db.session import get_db
from app.core.config import settings
from app.core.deps import get_current_user, require_role
from app.models.user import User
from app.models.holiday import Holiday, EmployeeOptionalHoliday
from app.models.enums import UserRole, HolidayType
from app.schemas.holiday import (
    HolidayListResponse,
    HolidayItem,
    HolidayCreate,
    HolidayDetail,
    SelectOptionalResponse,
)

router = APIRouter()


@router.get("", response_model=HolidayListResponse, summary="List holidays for a given year")
def list_holidays(
    year: Optional[int] = Query(None, description="Calendar year (defaults to current year)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve all holidays (mandatory, optional, festival) for the specified year.
    """
    target_year = year or datetime.now(timezone.utc).year
    stmt = (
        select(Holiday)
        .where(Holiday.year == target_year)
        .order_by(Holiday.date)
    )
    holidays = db.execute(stmt).scalars().all()

    items = [
        HolidayItem(
            id=h.id,
            name=h.name,
            date=h.date,
            type=h.type.value if hasattr(h.type, "value") else str(h.type)
        )
        for h in holidays
    ]
    return HolidayListResponse(items=items)


@router.post("", response_model=HolidayDetail, status_code=status.HTTP_201_CREATED, summary="Create a new holiday")
def create_holiday(
    holiday_in: HolidayCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.super_admin, UserRole.hr_admin]))
):
    """
    Add a company holiday (HR / Super Admin only).
    """
    holiday = Holiday(
        name=holiday_in.name,
        date=holiday_in.date,
        type=holiday_in.type,
        year=holiday_in.year or holiday_in.date.year,
        description=holiday_in.description
    )
    db.add(holiday)
    db.commit()
    db.refresh(holiday)

    return HolidayDetail(
        id=holiday.id,
        name=holiday.name,
        date=holiday.date,
        type=holiday.type.value if hasattr(holiday.type, "value") else str(holiday.type),
        year=holiday.year,
        description=holiday.description,
        created_at=holiday.created_at
    )


@router.post("/{id}/select-optional", response_model=SelectOptionalResponse, summary="Select an optional holiday")
def select_optional_holiday(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Employee selects an optional holiday, enforcing the maximum allowed limit per year.
    """
    if not current_user.employee_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not linked to an employee profile"
        )

    holiday = db.execute(select(Holiday).where(Holiday.id == id)).scalar_one_or_none()
    if not holiday:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holiday not found")

    if holiday.type != HolidayType.optional:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only holidays of type 'optional' can be selected"
        )

    # Check if already selected
    already_selected = db.execute(
        select(EmployeeOptionalHoliday).where(
            EmployeeOptionalHoliday.employee_id == current_user.employee_id,
            EmployeeOptionalHoliday.holiday_id == holiday.id
        )
    ).scalar_one_or_none()
    if already_selected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already selected this optional holiday"
        )

    # Count optional holidays selected by employee for this holiday's year
    count_query = (
        select(func.count(EmployeeOptionalHoliday.id))
        .join(Holiday, EmployeeOptionalHoliday.holiday_id == Holiday.id)
        .where(
            EmployeeOptionalHoliday.employee_id == current_user.employee_id,
            Holiday.year == holiday.year
        )
    )
    current_selected_count = db.execute(count_query).scalar() or 0

    max_allowed = settings.MAX_OPTIONAL_HOLIDAYS_PER_YEAR
    if current_selected_count >= max_allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You've already selected the maximum allowed optional holidays"
        )

    selection = EmployeeOptionalHoliday(
        employee_id=current_user.employee_id,
        holiday_id=holiday.id
    )
    db.add(selection)
    db.commit()
    db.refresh(selection)

    return SelectOptionalResponse(
        employee_id=selection.employee_id,
        holiday_id=selection.holiday_id,
        selected_at=selection.selected_at
    )
