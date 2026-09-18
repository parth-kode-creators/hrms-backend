from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status, Response
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, or_, extract

from app.db.session import get_db
from app.core.deps import get_current_user, require_role
from app.models.user import User
from app.models.employee import Employee
from app.models.leave import LeaveType, LeaveBalance, LeaveRequest
from app.models.enums import UserRole
from app.schemas.leave import (
    LeaveTypeListResponse,
    LeaveTypeItem,
    LeaveTypeCreate,
    LeaveBalanceMeResponse,
    LeaveBalanceItem,
    LeaveApplyRequest,
    LeaveApplyResponse,
    LeaveRejectRequest,
    LeaveDecisionResponse,
    LeaveRequestListResponse,
    LeaveRequestItem,
)
from app.services.leave_service import (
    calculate_requested_leave_days,
    check_leave_balance,
    check_overlapping_leaves,
    deduct_leave_balance,
)
from app.services.excel_service import export_leaves_to_excel, import_leaves_from_excel

router = APIRouter()


# ------------------ Leave Types ------------------ #

@router.get("/leave-types", response_model=LeaveTypeListResponse, summary="List all leave types")
def list_leave_types(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all available leave types in the organization.
    """
    types = db.execute(select(LeaveType).order_by(LeaveType.id)).scalars().all()
    items = [
        LeaveTypeItem(
            id=lt.id,
            name=lt.name,
            default_days_per_year=lt.default_days_per_year,
            is_paid=lt.is_paid
        )
        for lt in types
    ]
    return LeaveTypeListResponse(items=items)


@router.post("/leave-types", response_model=LeaveTypeItem, status_code=status.HTTP_201_CREATED, summary="Create leave type")
def create_leave_type(
    lt_in: LeaveTypeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.super_admin, UserRole.hr_admin]))
):
    """
    Add a new leave type policy (HR / Super Admin only).
    """
    existing = db.execute(select(LeaveType).where(LeaveType.name == lt_in.name)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Leave type '{lt_in.name}' already exists"
        )

    lt = LeaveType(
        name=lt_in.name,
        default_days_per_year=lt_in.default_days_per_year,
        is_paid=lt_in.is_paid,
        carry_forward=lt_in.carry_forward
    )
    db.add(lt)
    db.commit()
    db.refresh(lt)
    return LeaveTypeItem(
        id=lt.id,
        name=lt.name,
        default_days_per_year=lt.default_days_per_year,
        is_paid=lt.is_paid
    )


# ------------------ Leave Balances ------------------ #

@router.get("/leave/balance/me", response_model=LeaveBalanceMeResponse, summary="Get current employee's leave balance")
def get_my_leave_balances(
    year: Optional[int] = Query(None, description="Calendar year (default current)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve leave balances for the logged-in employee for the given year.
    """
    if not current_user.employee_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is not linked to an employee profile")

    target_year = year or datetime.now(timezone.utc).year
    stmt = (
        select(LeaveBalance)
        .options(joinedload(LeaveBalance.leave_type))
        .where(
            LeaveBalance.employee_id == current_user.employee_id,
            LeaveBalance.year == target_year
        )
        .order_by(LeaveBalance.leave_type_id)
    )
    balances = db.execute(stmt).scalars().all()

    items = [
        LeaveBalanceItem(
            leave_type=b.leave_type.name,
            total_allotted=float(b.total_allotted),
            used=float(b.used),
            balance=float(b.balance)
        )
        for b in balances
    ]
    return LeaveBalanceMeResponse(items=items)


# ------------------ Apply & Manage Requests ------------------ #

@router.post("/leave/apply", response_model=LeaveApplyResponse, status_code=status.HTTP_201_CREATED, summary="Apply for leave")
def apply_leave(
    req_in: LeaveApplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit a leave application with balance and overlap checks.
    """
    if not current_user.employee_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is not linked to an employee profile")

    # 1. Calculate requested days
    requested_days = calculate_requested_leave_days(
        db, req_in.start_date, req_in.end_date, req_in.is_half_day
    )

    # 2. Check balance sufficiency
    check_leave_balance(
        db, current_user.employee_id, req_in.leave_type_id, req_in.start_date.year, requested_days
    )

    # 3. Check overlapping leaves
    check_overlapping_leaves(db, current_user.employee_id, req_in.start_date, req_in.end_date)

    leave_req = LeaveRequest(
        employee_id=current_user.employee_id,
        leave_type_id=req_in.leave_type_id,
        start_date=req_in.start_date,
        end_date=req_in.end_date,
        is_half_day=req_in.is_half_day,
        reason=req_in.reason,
        status="pending"
    )
    db.add(leave_req)
    db.commit()
    db.refresh(leave_req)

    return LeaveApplyResponse(
        id=leave_req.id,
        status=leave_req.status,
        applied_at=leave_req.applied_at
    )


@router.put("/leave/{id}/approve", response_model=LeaveDecisionResponse, summary="Approve leave request")
def approve_leave(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.super_admin, UserRole.hr_admin, UserRole.manager]))
):
    """
    Approve a pending leave request and atomically deduct the employee's balance.
    """
    stmt = (
        select(LeaveRequest)
        .options(joinedload(LeaveRequest.employee))
        .where(LeaveRequest.id == id)
    )
    leave_req = db.execute(stmt).scalar_one_or_none()
    if not leave_req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")

    if leave_req.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Leave request is already {leave_req.status}"
        )

    # Manager authorization: can only approve direct reports
    if current_user.role == UserRole.manager:
        if not leave_req.employee or leave_req.employee.manager_id != current_user.employee_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only approve leaves for your direct reports"
            )

    deduct_leave_balance(db, leave_req, current_user.employee_id)
    db.commit()
    db.refresh(leave_req)

    return LeaveDecisionResponse(
        id=leave_req.id,
        status=leave_req.status,
        decided_at=leave_req.decided_at
    )


@router.put("/leave/{id}/reject", response_model=LeaveDecisionResponse, summary="Reject leave request")
def reject_leave(
    id: int,
    reject_in: LeaveRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.super_admin, UserRole.hr_admin, UserRole.manager]))
):
    """
    Reject a pending leave request with an optional comment.
    """
    stmt = (
        select(LeaveRequest)
        .options(joinedload(LeaveRequest.employee))
        .where(LeaveRequest.id == id)
    )
    leave_req = db.execute(stmt).scalar_one_or_none()
    if not leave_req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")

    if leave_req.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Leave request is already {leave_req.status}"
        )

    if current_user.role == UserRole.manager:
        if not leave_req.employee or leave_req.employee.manager_id != current_user.employee_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only reject leaves for your direct reports"
            )

    leave_req.status = "rejected"
    leave_req.approved_by = current_user.employee_id
    leave_req.decided_at = datetime.now(timezone.utc)
    if reject_in.comment:
        existing_reason = leave_req.reason or ""
        leave_req.reason = f"{existing_reason} | Rejection note: {reject_in.comment}".strip(" |")

    db.commit()
    db.refresh(leave_req)

    return LeaveDecisionResponse(
        id=leave_req.id,
        status=leave_req.status,
        decided_at=leave_req.decided_at
    )


@router.get("/leave/requests", response_model=LeaveRequestListResponse, summary="List leave requests with role scoping")
def list_leave_requests(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (pending, approved, rejected)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List leave requests with query-level role scoping.
    """
    stmt = (
        select(LeaveRequest)
        .options(
            joinedload(LeaveRequest.employee),
            joinedload(LeaveRequest.leave_type)
        )
    )

    if current_user.role in [UserRole.super_admin, UserRole.hr_admin]:
        pass
    elif current_user.role == UserRole.manager:
        stmt = stmt.join(Employee, LeaveRequest.employee_id == Employee.id).where(
            or_(
                Employee.id == current_user.employee_id,
                Employee.manager_id == current_user.employee_id
            )
        )
    else:
        stmt = stmt.where(LeaveRequest.employee_id == current_user.employee_id)

    if status_filter:
        stmt = stmt.where(LeaveRequest.status == status_filter)

    requests = db.execute(stmt.order_by(LeaveRequest.applied_at.desc())).scalars().all()

    items = [
        LeaveRequestItem(
            id=lr.id,
            employee_id=lr.employee_id,
            employee_name=lr.employee.full_name if lr.employee else None,
            leave_type=lr.leave_type.name,
            start_date=lr.start_date,
            end_date=lr.end_date,
            is_half_day=lr.is_half_day,
            reason=lr.reason,
            status=lr.status,
            applied_at=lr.applied_at,
            decided_at=lr.decided_at
        )
        for lr in requests
    ]
    return LeaveRequestListResponse(items=items)


# ------------------ Import / Export ------------------ #

@router.get("/leave/export", summary="Export leave requests to Excel")
def export_leaves(
    format: str = Query("xlsx"),
    employee_id: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export leave requests to downloadable Excel (.xlsx).
    """
    stmt = select(LeaveRequest).options(
        joinedload(LeaveRequest.employee),
        joinedload(LeaveRequest.leave_type)
    )

    if current_user.role in [UserRole.super_admin, UserRole.hr_admin]:
        if employee_id:
            stmt = stmt.where(LeaveRequest.employee_id == employee_id)
    elif current_user.role == UserRole.manager:
        stmt = stmt.join(Employee, LeaveRequest.employee_id == Employee.id).where(
            or_(Employee.id == current_user.employee_id, Employee.manager_id == current_user.employee_id)
        )
        if employee_id:
            stmt = stmt.where(LeaveRequest.employee_id == employee_id)
    else:
        stmt = stmt.where(LeaveRequest.employee_id == current_user.employee_id)

    if year:
        stmt = stmt.where(extract("year", LeaveRequest.start_date) == year)

    records = db.execute(stmt.order_by(LeaveRequest.applied_at.desc())).scalars().all()
    excel_stream = export_leaves_to_excel(records)

    filename = f"leave_requests_{year or 'all'}.xlsx"
    return Response(
        content=excel_stream.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/leave/import", summary="Bulk import leave balances from Excel")
def import_leaves(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.super_admin, UserRole.hr_admin]))
):
    """
    Bulk import/adjust leave balances from Excel spreadsheet (HR/Admin only).
    """
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="File must be an Excel document (.xlsx or .xls)")

    file_bytes = file.file.read()
    imported, skipped, errors = import_leaves_from_excel(file_bytes, db)
    return {"imported": imported, "skipped": skipped, "errors": errors}
