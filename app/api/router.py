from fastapi import APIRouter
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

api_router = APIRouter()

# Mount all API v1 modules
api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
api_router.include_router(departments_router, prefix="/departments", tags=["Departments"])
api_router.include_router(office_locations_router, prefix="/office-locations", tags=["Office Locations"])
api_router.include_router(employees_router, prefix="/employees", tags=["Employees"])
api_router.include_router(attendance_router, prefix="/attendance", tags=["Attendance"])
api_router.include_router(holidays_router, prefix="/holidays", tags=["Holidays"])
api_router.include_router(leaves_router, tags=["Leave"])
api_router.include_router(projects_router, prefix="/projects", tags=["Projects"])
api_router.include_router(tasks_router, prefix="/tasks", tags=["Tasks"])
api_router.include_router(calendar_router, prefix="/calendar", tags=["Calendar"])
api_router.include_router(reports_router, prefix="/reports", tags=["Reports"])
