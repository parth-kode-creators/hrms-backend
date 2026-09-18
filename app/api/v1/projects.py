from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import select, or_, func

from app.db.session import get_db
from app.core.deps import get_current_user, require_role
from app.models.user import User
from app.models.employee import Employee
from app.models.project import Project, ProjectMember
from app.models.task import Task
from app.models.enums import UserRole
from app.schemas.project import (
    ProjectCreate,
    ProjectRead,
    ProjectDetail,
    ProjectMemberCreate,
    ProjectMemberRead,
)

router = APIRouter()


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED, summary="Create project")
def create_project(
    proj_in: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.super_admin, UserRole.hr_admin, UserRole.manager]))
):
    """
    Create a new project (Manager / HR / Admin).
    """
    project = Project(
        name=proj_in.name,
        description=proj_in.description,
        start_date=proj_in.start_date,
        end_date=proj_in.end_date,
        status=proj_in.status or "active",
        created_by=current_user.employee_id
    )
    db.add(project)
    db.flush()

    # Automatically add creator as manager/member
    if current_user.employee_id:
        member = ProjectMember(
            project_id=project.id,
            employee_id=current_user.employee_id,
            role_in_project="manager" if current_user.role == UserRole.manager else "owner"
        )
        db.add(member)

    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=List[ProjectRead], summary="List projects")
def list_projects(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (e.g. active)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List projects visible to user.
    - HR / Super Admin: All projects
    - Manager / Employee: Projects created by self or where user is a member
    """
    stmt = select(Project)

    if current_user.role in [UserRole.super_admin, UserRole.hr_admin]:
        pass
    else:
        member_proj_ids = select(ProjectMember.project_id).where(
            ProjectMember.employee_id == current_user.employee_id
        )
        stmt = stmt.where(
            or_(
                Project.created_by == current_user.employee_id,
                Project.id.in_(member_proj_ids)
            )
        )

    if status_filter:
        stmt = stmt.where(Project.status == status_filter)

    projects = db.execute(stmt.order_by(Project.created_at.desc())).scalars().all()
    return projects


@router.get("/{id}", response_model=ProjectDetail, summary="Get project details")
def get_project(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed project profile with members and task count.
    """
    stmt = (
        select(Project)
        .options(
            selectinload(Project.members).joinedload(ProjectMember.employee)
        )
        .where(Project.id == id)
    )
    project = db.execute(stmt).unique().scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Member list
    members = [
        ProjectMemberRead(
            project_id=m.project_id,
            employee_id=m.employee_id,
            role_in_project=m.role_in_project,
            employee_name=m.employee.full_name if m.employee else None
        )
        for m in project.members
    ]

    task_count = db.execute(select(func.count(Task.id)).where(Task.project_id == id)).scalar() or 0

    return ProjectDetail(
        id=project.id,
        name=project.name,
        description=project.description,
        start_date=project.start_date,
        end_date=project.end_date,
        status=project.status,
        created_by=project.created_by,
        created_at=project.created_at,
        members=members,
        task_count=task_count
    )


@router.post("/{id}/members", response_model=ProjectMemberRead, status_code=status.HTTP_201_CREATED, summary="Add project member")
def add_project_member(
    id: int,
    member_in: ProjectMemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.super_admin, UserRole.hr_admin, UserRole.manager]))
):
    """
    Assign an employee to a project (Manager / HR only).
    """
    project = db.execute(select(Project).where(Project.id == id)).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    employee = db.execute(select(Employee).where(Employee.id == member_in.employee_id)).scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    existing = db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == id,
            ProjectMember.employee_id == member_in.employee_id
        )
    ).scalar_one_or_none()

    if existing:
        existing.role_in_project = member_in.role_in_project
        db.commit()
        return ProjectMemberRead(
            project_id=id,
            employee_id=employee.id,
            role_in_project=existing.role_in_project,
            employee_name=employee.full_name
        )

    new_member = ProjectMember(
        project_id=id,
        employee_id=member_in.employee_id,
        role_in_project=member_in.role_in_project or "contributor"
    )
    db.add(new_member)
    db.commit()

    return ProjectMemberRead(
        project_id=id,
        employee_id=employee.id,
        role_in_project=new_member.role_in_project,
        employee_name=employee.full_name
    )
