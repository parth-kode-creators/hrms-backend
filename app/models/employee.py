from sqlalchemy import String, Text, Date, DateTime, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import date, datetime
from typing import Optional, List, TYPE_CHECKING
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.department import Department
    from app.models.office_location import OfficeLocation
    from app.models.user import User
    from app.models.attendance import Attendance
    from app.models.leave import LeaveBalance, LeaveRequest
    from app.models.task import Task, TaskLog
    from app.models.notification import Notification


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    designation: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    date_of_joining: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    manager_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True
    )
    office_location_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("office_locations.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="active")
    profile_photo_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    emergency_contact: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    department: Mapped[Optional["Department"]] = relationship("Department", back_populates="employees")
    office_location: Mapped[Optional["OfficeLocation"]] = relationship(
        "OfficeLocation", back_populates="employees"
    )
    manager: Mapped[Optional["Employee"]] = relationship(
        "Employee", remote_side=[id], back_populates="direct_reports"
    )
    direct_reports: Mapped[List["Employee"]] = relationship(
        "Employee", back_populates="manager"
    )
    user: Mapped[Optional["User"]] = relationship(
        "User", back_populates="employee", uselist=False, cascade="all, delete-orphan"
    )
    documents: Mapped[List["EmployeeDocument"]] = relationship(
        "EmployeeDocument", back_populates="employee", cascade="all, delete-orphan"
    )
    attendance_records: Mapped[List["Attendance"]] = relationship(
        "Attendance", back_populates="employee", cascade="all, delete-orphan"
    )
    leave_balances: Mapped[List["LeaveBalance"]] = relationship(
        "LeaveBalance", back_populates="employee", cascade="all, delete-orphan"
    )
    leave_requests: Mapped[List["LeaveRequest"]] = relationship(
        "LeaveRequest", foreign_keys="LeaveRequest.employee_id", back_populates="employee", cascade="all, delete-orphan"
    )
    assigned_tasks: Mapped[List["Task"]] = relationship(
        "Task", foreign_keys="Task.assigned_to", back_populates="assignee"
    )
    task_logs: Mapped[List["TaskLog"]] = relationship(
        "TaskLog", back_populates="employee", cascade="all, delete-orphan"
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification", back_populates="employee", cascade="all, delete-orphan"
    )


class EmployeeDocument(Base):
    __tablename__ = "employee_documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    doc_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    employee: Mapped["Employee"] = relationship("Employee", back_populates="documents")
