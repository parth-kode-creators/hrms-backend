from typing import Optional, List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select

from app.db.session import get_db
from app.core.deps import get_current_user, require_role
from app.models.user import User
from app.models.employee import Employee
from app.models.project import Project, ProjectMember
from app.models.task import Task, TaskLog
from app.models.notification import Notification
from app.models.enums import UserRole
from app.schemas.task import (
    TaskCreate,
    TaskUpdate,
    TaskRead,
    TaskMyResponse,
    TaskMyItem,
    TaskLogCreate,
    TaskLogRead,
    TaskLogSimple,
)

router = APIRouter()


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED, summary="Create task")
def create_task(
    task_in: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.super_admin, UserRole.hr_admin, UserRole.manager]))
):
    """
    Create a project task and assign it to an employee (Manager / HR only).
    """
    project = db.execute(select(Project).where(Project.id == task_in.project_id)).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if task_in.assigned_to:
        assignee = db.execute(select(Employee).where(Employee.id == task_in.assigned_to)).scalar_one_or_none()
        if not assignee:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee employee not found")

    task = Task(
        project_id=task_in.project_id,
        assigned_to=task_in.assigned_to,
        title=task_in.title,
        description=task_in.description,
        status=task_in.status or "pending",
        priority=task_in.priority or "medium",
        due_date=task_in.due_date
    )
    db.add(task)
    db.flush()

    # Send in-app notification if assigned
    if task.assigned_to:
        notification = Notification(
            employee_id=task.assigned_to,
            title="Task Assigned",
            body=f"You have been assigned to task: '{task.title}' in project '{project.name}'",
            type="task_assigned"
        )
        db.add(notification)

    db.commit()
    db.refresh(task)
    return task


@router.get("/me", response_model=TaskMyResponse, summary="Get current employee's assigned tasks")
def get_my_tasks(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (pending, in_progress, completed, blocked)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve all tasks assigned to the currently logged-in employee.
    """
    if not current_user.employee_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User has no employee profile")

    stmt = (
        select(Task)
        .options(joinedload(Task.project))
        .where(Task.assigned_to == current_user.employee_id)
    )

    if status_filter:
        stmt = stmt.where(Task.status == status_filter)

    tasks = db.execute(stmt.order_by(Task.due_date.asc().nullslast())).scalars().all()

    items = [
        TaskMyItem(
            id=t.id,
            title=t.title,
            project=t.project.name if t.project else "Unknown Project",
            status=t.status,
            priority=t.priority,
            due_date=t.due_date
        )
        for t in tasks
    ]
    return TaskMyResponse(items=items)


@router.put("/{id}", response_model=TaskRead, summary="Update task status or details")
def update_task(
    id: int,
    task_in: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a task:
    - Assigned employee: can update status (in_progress, completed, blocked).
    - Manager / HR: can update all details.
    """
    task = db.execute(select(Task).where(Task.id == id)).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    is_manager = current_user.role in [UserRole.super_admin, UserRole.hr_admin, UserRole.manager]
    is_assignee = task.assigned_to == current_user.employee_id

    if not is_manager and not is_assignee:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update tasks assigned to you"
        )

    # Assignees can update status
    if task_in.status is not None:
        task.status = task_in.status

    # Manager can update other fields
    if is_manager:
        if task_in.title is not None:
            task.title = task_in.title
        if task_in.description is not None:
            task.description = task_in.description
        if task_in.priority is not None:
            task.priority = task_in.priority
        if task_in.due_date is not None:
            task.due_date = task_in.due_date
        if task_in.assigned_to is not None:
            task.assigned_to = task_in.assigned_to

    task.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)
    return task


@router.post("/{id}/log", response_model=TaskLogSimple, status_code=status.HTTP_201_CREATED, summary="Log hours worked on task")
def log_task_work(
    id: int,
    log_in: TaskLogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Record daily hours and work notes for a task.
    """
    if not current_user.employee_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User has no employee profile")

    task = db.execute(select(Task).where(Task.id == id)).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    log_entry = TaskLog(
        task_id=task.id,
        employee_id=current_user.employee_id,
        log_date=log_in.log_date,
        hours_spent=log_in.hours_spent,
        notes=log_in.notes
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)

    return TaskLogSimple(
        id=log_entry.id,
        task_id=log_entry.task_id,
        hours_spent=float(log_entry.hours_spent)
    )


@router.get("/{id}/logs", response_model=List[TaskLogRead], summary="Get work logs for task")
def get_task_logs(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve historical work logs for a specific task.
    """
    logs = db.execute(
        select(TaskLog).where(TaskLog.task_id == id).order_by(TaskLog.log_date.desc())
    ).scalars().all()

    return [
        TaskLogRead(
            id=l.id,
            task_id=l.task_id,
            employee_id=l.employee_id,
            log_date=l.log_date,
            hours_spent=float(l.hours_spent),
            notes=l.notes,
            created_at=l.created_at
        )
        for l in logs
    ]
