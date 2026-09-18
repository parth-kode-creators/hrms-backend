from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.core.deps import get_current_user, require_role
from app.models.department import Department
from app.models.enums import UserRole
from app.schemas.department import DepartmentRead, DepartmentCreate

router = APIRouter()


@router.get("", response_model=List[DepartmentRead], summary="List all departments")
def list_departments(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get all company departments.
    """
    departments = db.execute(select(Department).order_by(Department.name)).scalars().all()
    return departments


@router.post("", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED, summary="Create department")
def create_department(
    dept_in: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_role([UserRole.super_admin, UserRole.hr_admin]))
):
    """
    Create a new department (HR / Super Admin only).
    """
    existing = db.execute(select(Department).where(Department.name == dept_in.name)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Department '{dept_in.name}' already exists"
        )
    dept = Department(name=dept_in.name)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept
