from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, func, or_

from app.db.session import get_db
from app.core.deps import get_current_user, require_role
from app.core.security import get_password_hash
from app.models.employee import Employee
from app.models.user import User
from app.models.department import Department
from app.models.office_location import OfficeLocation
from app.models.enums import UserRole
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeDetail,
    EmployeeListResponse,
    EmployeeListItem,
)
from app.services.employee_service import generate_next_employee_code, initialize_leave_balances

router = APIRouter()


@router.post("", response_model=EmployeeDetail, status_code=status.HTTP_201_CREATED, summary="Create employee")
def create_employee(
    emp_in: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.super_admin, UserRole.hr_admin]))
):
    """
    Create a new employee (HR / Super Admin only).
    Automatically generates employee code, user login credentials, and initial leave balances.
    """
    clean_email = emp_in.email.lower().strip()
    # Check email duplicate in employees
    if db.execute(select(Employee).where(Employee.email == clean_email)).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Employee with this email already exists"
        )
    # Check email duplicate in users
    if db.execute(select(User).where(User.email == clean_email)).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account with this email already exists"
        )

    # Validate department if provided
    if emp_in.department_id:
        if not db.execute(select(Department).where(Department.id == emp_in.department_id)).scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid department_id")

    # Validate office location if provided
    if emp_in.office_location_id:
        if not db.execute(select(OfficeLocation).where(OfficeLocation.id == emp_in.office_location_id)).scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid office_location_id")

    # Validate manager if provided
    if emp_in.manager_id:
        if not db.execute(select(Employee).where(Employee.id == emp_in.manager_id)).scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid manager_id")

    emp_code = generate_next_employee_code(db)

    new_emp = Employee(
        employee_code=emp_code,
        full_name=emp_in.full_name,
        email=clean_email,
        phone=emp_in.phone,
        department_id=emp_in.department_id,
        designation=emp_in.designation,
        date_of_joining=emp_in.date_of_joining,
        manager_id=emp_in.manager_id,
        office_location_id=emp_in.office_location_id,
        status=emp_in.status or "active"
    )
    db.add(new_emp)
    db.flush()

    # Create linked user account
    user_account = User(
        employee_id=new_emp.id,
        email=clean_email,
        password_hash=get_password_hash(emp_in.password or "DefaultPassword123!"),
        role=emp_in.role or UserRole.employee,
        is_active=True
    )
    db.add(user_account)

    # Initialize leave balances for current year
    initialize_leave_balances(db, new_emp.id)

    db.commit()

    # Reload with joined relations for response
    stmt = (
        select(Employee)
        .options(
            joinedload(Employee.department),
            joinedload(Employee.manager),
            joinedload(Employee.office_location)
        )
        .where(Employee.id == new_emp.id)
    )
    created_emp = db.execute(stmt).scalar_one()
    return created_emp


@router.get("", response_model=EmployeeListResponse, summary="List employees with role-scoped query")
def list_employees(
    department_id: Optional[int] = Query(None, description="Filter by department ID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (e.g. active)"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List employees with role-based visibility:
    - Super Admin / HR Admin: Company-wide view
    - Manager: Direct reports and self
    - Employee: Self-only view
    """
    query = select(Employee).options(joinedload(Employee.department))

    # Apply query-level role scoping
    if current_user.role in [UserRole.super_admin, UserRole.hr_admin]:
        pass  # Global visibility
    elif current_user.role == UserRole.manager:
        query = query.where(
            or_(
                Employee.id == current_user.employee_id,
                Employee.manager_id == current_user.employee_id
            )
        )
    else:
        # Standard employee visibility restricted strictly to self
        query = query.where(Employee.id == current_user.employee_id)

    # Apply filters
    if department_id:
        query = query.where(Employee.department_id == department_id)
    if status_filter:
        query = query.where(Employee.status == status_filter)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar() or 0

    # Paginate
    offset = (page - 1) * limit
    paged_query = query.order_by(Employee.id).offset(offset).limit(limit)
    employees = db.execute(paged_query).scalars().all()

    items = [
        EmployeeListItem(
            id=emp.id,
            full_name=emp.full_name,
            designation=emp.designation,
            department=emp.department.name if emp.department else None,
            status=emp.status
        )
        for emp in employees
    ]

    return EmployeeListResponse(total=total, page=page, items=items)


@router.get("/{id}", response_model=EmployeeDetail, summary="Get employee details")
def get_employee(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed profile of a specific employee.
    Enforces reporting line and self-visibility scoping.
    """
    stmt = (
        select(Employee)
        .options(
            joinedload(Employee.department),
            joinedload(Employee.manager),
            joinedload(Employee.office_location)
        )
        .where(Employee.id == id)
    )
    emp = db.execute(stmt).scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    # Check permissions
    if current_user.role in [UserRole.super_admin, UserRole.hr_admin]:
        pass
    elif current_user.role == UserRole.manager:
        if emp.id != current_user.employee_id and emp.manager_id != current_user.employee_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view profiles of yourself or your direct reports"
            )
    else:
        if emp.id != current_user.employee_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own profile"
            )

    return emp


@router.put("/{id}", response_model=EmployeeDetail, summary="Update employee profile")
def update_employee(
    id: int,
    emp_in: EmployeeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update employee information.
    - HR / Super Admin: Can update any field.
    - Employee: Can only update phone, address, emergency_contact, and profile_photo_url on their own profile.
    """
    stmt = (
        select(Employee)
        .options(
            joinedload(Employee.department),
            joinedload(Employee.manager),
            joinedload(Employee.office_location)
        )
        .where(Employee.id == id)
    )
    emp = db.execute(stmt).scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    is_admin = current_user.role in [UserRole.super_admin, UserRole.hr_admin]

    if not is_admin:
        # Non-admins can only update their own record
        if emp.id != current_user.employee_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own profile"
            )
        # Check if non-admin attempted to update administrative fields
        disallowed_changes = [
            emp_in.full_name is not None,
            emp_in.department_id is not None,
            emp_in.designation is not None,
            emp_in.date_of_joining is not None,
            emp_in.manager_id is not None,
            emp_in.office_location_id is not None,
            emp_in.status is not None,
        ]
        if any(disallowed_changes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Employees can only update phone, address, emergency contact, and profile photo"
            )

    # Apply updates
    if emp_in.phone is not None:
        emp.phone = emp_in.phone
    if emp_in.address is not None:
        emp.address = emp_in.address
    if emp_in.emergency_contact is not None:
        emp.emergency_contact = emp_in.emergency_contact
    if emp_in.profile_photo_url is not None:
        emp.profile_photo_url = emp_in.profile_photo_url

    if is_admin:
        if emp_in.full_name is not None:
            emp.full_name = emp_in.full_name
        if emp_in.department_id is not None:
            emp.department_id = emp_in.department_id
        if emp_in.designation is not None:
            emp.designation = emp_in.designation
        if emp_in.date_of_joining is not None:
            emp.date_of_joining = emp_in.date_of_joining
        if emp_in.manager_id is not None:
            emp.manager_id = emp_in.manager_id
        if emp_in.office_location_id is not None:
            emp.office_location_id = emp_in.office_location_id
        if emp_in.status is not None:
            emp.status = emp_in.status

    db.commit()
    db.refresh(emp)
    return emp


@router.delete("/{id}", status_code=status.HTTP_200_OK, summary="Delete or deactivate employee")
def delete_employee(
    id: int,
    hard_delete: bool = Query(False, description="Permanently delete instead of deactivating"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.super_admin, UserRole.hr_admin]))
):
    """
    Deactivate or permanently delete an employee (HR / Super Admin only).
    - Default (hard_delete=false): Sets employee status to 'inactive' and deactivates linked user login.
    - Permanent (hard_delete=true): Removes employee record from database.
    """
    emp = db.execute(select(Employee).where(Employee.id == id)).scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    # Prevent admin from deactivating or deleting themselves
    if emp.id == current_user.employee_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete or deactivate your own account"
        )

    if hard_delete:
        try:
            db.delete(emp)
            db.commit()
            return {"status": "success", "message": f"Employee {emp.full_name} permanently deleted"}
        except Exception:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot permanently delete employee due to existing related records. Deactivate instead."
            )
    else:
        emp.status = "inactive"
        user = db.execute(select(User).where(User.employee_id == emp.id)).scalar_one_or_none()
        if user:
            user.is_active = False
        db.commit()
        return {"status": "success", "message": f"Employee {emp.full_name} deactivated successfully"}

