from app.api.v1.auth import router as auth_router
from app.api.v1.departments import router as departments_router
from app.api.v1.office_locations import router as office_locations_router
from app.api.v1.employees import router as employees_router
from app.api.v1.attendance import router as attendance_router
from app.api.v1.holidays import router as holidays_router
from app.api.v1.leaves import router as leaves_router
from app.api.v1.projects import router as projects_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.calendar import router as calendar_router
from app.api.v1.reports import router as reports_router

__all__ = [
    "auth_router",
    "departments_router",
    "office_locations_router",
    "employees_router",
    "attendance_router",
    "holidays_router",
    "leaves_router",
    "projects_router",
    "tasks_router",
    "calendar_router",
    "reports_router",
]
