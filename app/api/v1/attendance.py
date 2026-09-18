from datetime import datetime, date, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request, status, Response
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, and_, extract

from app.db.session import get_db
from app.core.deps import get_current_user, require_role
from app.models.user import User
from app.models.employee import Employee
from app.models.attendance import Attendance, AttendanceRegularizationRequest
from app.models.enums import UserRole, CheckMethod
from app.schemas.attendance import (
    CheckInRequest,
    CheckInResponse,
    CheckOutRequest,
    CheckOutResponse,
    AttendanceMeResponse,
    AttendanceLogItem,
    RegularizeRequest,
    RegularizeResponse,
    ApproveRegularizeRequest,
    WFHRequest,
    WFHResponse,
    ImportResponse,
)
from app.services.attendance_service import validate_geofence, calculate_total_hours
from app.services.excel_service import export_attendance_to_excel, import_attendance_from_excel

router = APIRouter()


@router.post("/check-in", response_model=CheckInResponse, summary="Employee Check-In")
def check_in(
    check_in_req: CheckInRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Clock in for today with server-side geofencing and IP validation.
    """
    if not current_user.employee_id or not current_user.employee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not linked to an employee profile"
        )

    employee = current_user.employee
    today = datetime.now(timezone.utc).date()
    now_dt = datetime.now(timezone.utc)

    # Validate geofence if mobile_geofence method is used
    if check_in_req.method == CheckMethod.mobile_geofence:
        if check_in_req.lat is None or check_in_req.lng is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Coordinates (lat, lng) are required for mobile geofence check-in"
            )
        validate_geofence(db, employee, check_in_req.lat, check_in_req.lng)

    # Capture IP
    client_ip = request.client.host if request.client else None

    # Check existing attendance record for today
    att = db.execute(
        select(Attendance).where(
            Attendance.employee_id == employee.id,
            Attendance.date == today
        )
    ).scalar_one_or_none()

    if att and att.check_in_time is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Already checked in today at {att.check_in_time.strftime('%H:%M:%S')}"
        )

    if not att:
        att = Attendance(
            employee_id=employee.id,
            date=today,
            check_in_time=now_dt,
            check_in_method=check_in_req.method,
            check_in_lat=check_in_req.lat,
            check_in_lng=check_in_req.lng,
            check_in_ip=client_ip,
            status="present"
        )
        db.add(att)
    else:
        att.check_in_time = now_dt
        att.check_in_method = check_in_req.method
        att.check_in_lat = check_in_req.lat
        att.check_in_lng = check_in_req.lng
        att.check_in_ip = client_ip
        att.status = "present"

    db.commit()
    db.refresh(att)
    return att


@router.post("/check-out", response_model=CheckOutResponse, summary="Employee Check-Out")
def check_out(
    check_out_req: CheckOutRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Clock out for today and compute total hours.
    """
    if not current_user.employee_id or not current_user.employee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not linked to an employee profile"
        )

    employee = current_user.employee
    today = datetime.now(timezone.utc).date()
    now_dt = datetime.now(timezone.utc)

    # Validate geofence if mobile_geofence method is used
    if check_out_req.method == CheckMethod.mobile_geofence:
        if check_out_req.lat is not None and check_out_req.lng is not None:
            validate_geofence(db, employee, check_out_req.lat, check_out_req.lng)

    att = db.execute(
        select(Attendance).where(
            Attendance.employee_id == employee.id,
            Attendance.date == today
        )
    ).scalar_one_or_none()

    if not att or not att.check_in_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No check-in record found for today"
        )

    att.check_out_time = now_dt
    att.check_out_method = check_out_req.method
    att.total_hours = calculate_total_hours(att.check_in_time, now_dt)

    db.commit()
    db.refresh(att)

    return CheckOutResponse(
        id=att.id,
        check_out_time=att.check_out_time,
        total_hours=float(att.total_hours)
    )


@router.get("/me", response_model=AttendanceMeResponse, summary="Get current employee's monthly attendance")
def get_my_attendance(
    month: Optional[int] = Query(None, ge=1, le=12, description="Month (1-12)"),
    year: Optional[int] = Query(None, description="Year (e.g. 2026)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve monthly attendance history for currently logged-in employee.
    """
    if not current_user.employee_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User has no employee profile")

    now = datetime.now(timezone.utc)
    target_month = month or now.month
    target_year = year or now.year

    stmt = (
        select(Attendance)
        .where(
            Attendance.employee_id == current_user.employee_id,
            extract("month", Attendance.date) == target_month,
            extract("year", Attendance.date) == target_year
        )
        .order_by(Attendance.date.desc())
    )
    records = db.execute(stmt).scalars().all()

    items = [
        AttendanceLogItem(
            date=r.date.strftime("%Y-%m-%d"),
            check_in_time=r.check_in_time.strftime("%H:%M") if r.check_in_time else None,
            check_out_time=r.check_out_time.strftime("%H:%M") if r.check_out_time else None,
            total_hours=float(r.total_hours) if r.total_hours is not None else None,
            status=r.status
        )
        for r in records
    ]
    return AttendanceMeResponse(items=items)


@router.post("/regularize", response_model=RegularizeResponse, summary="Submit attendance regularization request")
def regularize_attendance(
    reg_in: RegularizeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Request attendance regularization for missed or incorrect check-in/out.
    """
    att = db.execute(select(Attendance).where(Attendance.id == reg_in.attendance_id)).scalar_one_or_none()
    if not att:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance record not found")

    if att.employee_id != current_user.employee_id and current_user.role not in [UserRole.super_admin, UserRole.hr_admin]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot regularize another employee's attendance")

    reg_req = AttendanceRegularizationRequest(
        attendance_id=att.id,
        employee_id=att.employee_id,
        requested_check_in=reg_in.requested_check_in,
        requested_check_out=reg_in.requested_check_out,
        reason=reg_in.reason,
        status="pending"
    )
    db.add(reg_req)
    db.commit()
    db.refresh(reg_req)

    return RegularizeResponse(id=reg_req.id, status=reg_req.status)


@router.put("/regularize/{id}/approve", response_model=RegularizeResponse, summary="Approve/Reject attendance regularization")
def decide_regularization(
    id: int,
    decision: ApproveRegularizeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.super_admin, UserRole.hr_admin, UserRole.manager]))
):
    """
    Manager or HR approves or rejects an attendance regularization request.
    """
    stmt = (
        select(AttendanceRegularizationRequest)
        .options(
            joinedload(AttendanceRegularizationRequest.attendance),
            joinedload(AttendanceRegularizationRequest.employee)
        )
        .where(AttendanceRegularizationRequest.id == id)
    )
    reg_req = db.execute(stmt).scalar_one_or_none()
    if not reg_req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Regularization request not found")

    # If manager, verify target employee reports to current manager
    if current_user.role == UserRole.manager:
        if not reg_req.employee or reg_req.employee.manager_id != current_user.employee_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only approve regularization for your direct reports"
            )

    reg_req.approved_by = current_user.employee_id

    if decision.approve:
        reg_req.status = "approved"
        # Update linked attendance record
        att = reg_req.attendance
        if reg_req.requested_check_in:
            att.check_in_time = reg_req.requested_check_in
        if reg_req.requested_check_out:
            att.check_out_time = reg_req.requested_check_out

        if att.check_in_time and att.check_out_time:
            att.total_hours = calculate_total_hours(att.check_in_time, att.check_out_time)

        att.is_regularized = True
        att.regularize_reason = reg_req.reason
    else:
        reg_req.status = "rejected"

    db.commit()
    db.refresh(reg_req)
    return RegularizeResponse(id=reg_req.id, status=reg_req.status)


@router.post("/wfh-request", response_model=WFHResponse, summary="Request Work From Home (WFH)")
def request_wfh(
    wfh_in: WFHRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit a Work From Home attendance request.
    """
    if not current_user.employee_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User has no employee profile")

    # Check if attendance already exists for that date
    att = db.execute(
        select(Attendance).where(
            Attendance.employee_id == current_user.employee_id,
            Attendance.date == wfh_in.date
        )
    ).scalar_one_or_none()

    if not att:
        att = Attendance(
            employee_id=current_user.employee_id,
            date=wfh_in.date,
            status="wfh_pending_approval",
            regularize_reason=wfh_in.reason,
            check_in_method=CheckMethod.manual_override
        )
        db.add(att)
    else:
        att.status = "wfh_pending_approval"
        att.regularize_reason = wfh_in.reason

    db.commit()
    db.refresh(att)
    return WFHResponse(id=att.id, status=att.status)


@router.get("/export", summary="Export attendance to Excel (.xlsx)")
def export_attendance(
    format: str = Query("xlsx", description="File format (xlsx)"),
    employee_id: Optional[int] = Query(None, description="Filter by employee ID"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Filter by month"),
    year: Optional[int] = Query(None, description="Filter by year"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export attendance records to downloadable Excel workbook.
    """
    stmt = select(Attendance).options(joinedload(Attendance.employee))

    # Apply role scoping
    if current_user.role in [UserRole.super_admin, UserRole.hr_admin]:
        if employee_id:
            stmt = stmt.where(Attendance.employee_id == employee_id)
    elif current_user.role == UserRole.manager:
        if employee_id:
            stmt = stmt.join(Employee, Attendance.employee_id == Employee.id).where(
                Attendance.employee_id == employee_id,
                or_(Employee.id == current_user.employee_id, Employee.manager_id == current_user.employee_id)
            )
        else:
            stmt = stmt.join(Employee, Attendance.employee_id == Employee.id).where(
                or_(Employee.id == current_user.employee_id, Employee.manager_id == current_user.employee_id)
            )
    else:
        # Standard employee can only export their own records
        stmt = stmt.where(Attendance.employee_id == current_user.employee_id)

    if month:
        stmt = stmt.where(extract("month", Attendance.date) == month)
    if year:
        stmt = stmt.where(extract("year", Attendance.date) == year)

    records = db.execute(stmt.order_by(Attendance.date.desc())).scalars().all()
    excel_stream = export_attendance_to_excel(records)

    filename = f"attendance_report_{year or 'all'}_{month or 'all'}.xlsx"
    return Response(
        content=excel_stream.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/import", response_model=ImportResponse, summary="Import attendance from Excel (.xlsx)")
def import_attendance(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.super_admin, UserRole.hr_admin]))
):
    """
    Bulk import attendance records from Excel spreadsheet (HR/Admin only).
    """
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an Excel document (.xlsx or .xls)"
        )

    file_bytes = file.file.read()
    try:
        imported, skipped, errors = import_attendance_from_excel(file_bytes, db)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse Excel file: {str(e)}"
        )

    return ImportResponse(
        imported=imported,
        skipped=skipped,
        errors=errors
    )
