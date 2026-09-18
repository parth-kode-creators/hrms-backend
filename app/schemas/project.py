from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import date, datetime
from app.models.enums import ProjectStatus


class ProjectMemberCreate(BaseModel):
    employee_id: int
    role_in_project: Optional[str] = "contributor"


class ProjectMemberRead(BaseModel):
    project_id: int
    employee_id: int
    role_in_project: Optional[str] = None
    employee_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = "active"


class ProjectRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: str
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ProjectDetail(ProjectRead):
    members: List[ProjectMemberRead] = []
    task_count: int = 0
