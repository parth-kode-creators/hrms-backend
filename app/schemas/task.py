from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import date, datetime
from app.models.enums import TaskStatus, TaskPriority


class TaskCreate(BaseModel):
    project_id: int
    assigned_to: Optional[int] = None
    title: str
    description: Optional[str] = None
    status: Optional[str] = "pending"
    priority: Optional[str] = "medium"
    due_date: Optional[date] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[date] = None
    assigned_to: Optional[int] = None


class TaskRead(BaseModel):
    id: int
    project_id: int
    assigned_to: Optional[int] = None
    title: str
    description: Optional[str] = None
    status: str
    priority: str
    due_date: Optional[date] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TaskMyItem(BaseModel):
    id: int
    title: str
    project: str
    status: str
    priority: str
    due_date: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)


class TaskMyResponse(BaseModel):
    items: List[TaskMyItem]


class TaskLogCreate(BaseModel):
    log_date: date
    hours_spent: float
    notes: Optional[str] = None


class TaskLogRead(BaseModel):
    id: int
    task_id: int
    employee_id: int
    log_date: date
    hours_spent: float
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TaskLogSimple(BaseModel):
    id: int
    task_id: int
    hours_spent: float

    model_config = ConfigDict(from_attributes=True)
