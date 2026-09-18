import enum


class UserRole(str, enum.Enum):
    super_admin = "super_admin"
    hr_admin = "hr_admin"
    manager = "manager"
    employee = "employee"


class HolidayType(str, enum.Enum):
    mandatory = "mandatory"
    optional = "optional"
    festival = "festival"


class CheckMethod(str, enum.Enum):
    web_lan = "web_lan"
    mobile_geofence = "mobile_geofence"
    manual_override = "manual_override"


class RegularizationStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class LeaveRequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ProjectStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    on_hold = "on_hold"


class TaskStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    blocked = "blocked"


class TaskPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"
