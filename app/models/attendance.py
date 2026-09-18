from sqlalchemy import String, Text, Date, DateTime, Numeric, Boolean, Integer, ForeignKey, Enum as SQLEnum, UniqueConstraint, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import date, datetime
from typing import Optional, List, TYPE_CHECKING
from app.db.base import Base
from app.models.enums import CheckMethod

if TYPE_CHECKING:
    from app.models.employee import Employee


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("employee_id", "date", name="uq_attendance_emp_date"),
        Index("idx_attendance_emp_date", "employee_id", "date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    check_in_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    check_out_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    check_in_method: Mapped[Optional[CheckMethod]] = mapped_column(
        SQLEnum(CheckMethod, name="check_method", native_enum=True),
        nullable=True
    )
    check_out_method: Mapped[Optional[CheckMethod]] = mapped_column(
        SQLEnum(CheckMethod, name="check_method", native_enum=True),
        nullable=True
    )
    check_in_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    check_in_lat: Mapped[Optional[float]] = mapped_column(Numeric(9, 6), nullable=True)
    check_in_lng: Mapped[Optional[float]] = mapped_column(Numeric(9, 6), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="present")
    is_regularized: Mapped[bool] = mapped_column(Boolean, default=False)
    regularize_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_hours: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    employee: Mapped["Employee"] = relationship("Employee", back_populates="attendance_records")
    regularization_requests: Mapped[List["AttendanceRegularizationRequest"]] = relationship(
        "AttendanceRegularizationRequest", back_populates="attendance", cascade="all, delete-orphan"
    )


class AttendanceRegularizationRequest(Base):
    __tablename__ = "attendance_regularization_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    attendance_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("attendance.id", ondelete="CASCADE"), nullable=False
    )
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requested_check_in: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    requested_check_out: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    approved_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    attendance: Mapped["Attendance"] = relationship("Attendance", back_populates="regularization_requests")
    employee: Mapped["Employee"] = relationship("Employee", foreign_keys=[employee_id])
    approver: Mapped[Optional["Employee"]] = relationship("Employee", foreign_keys=[approved_by])
