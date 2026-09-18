import io
import uuid
from datetime import datetime, date, timezone
import openpyxl
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)


def get_admin_token() -> str:
    res = client.post("/auth/login", json={
        "email": settings.FIRST_SUPER_ADMIN_EMAIL,
        "password": settings.FIRST_SUPER_ADMIN_PASSWORD
    })
    return res.json()["access_token"]


def create_test_employee(role: str = "employee") -> dict:
    admin_token = get_admin_token()
    headers = {"Authorization": f"Bearer {admin_token}"}
    uid = uuid.uuid4().hex[:6]
    email = f"att.user.{uid}@company.com"
    pwd = "Password123!"

    create_res = client.post("/employees", json={
        "full_name": f"Attendance Tester {uid}",
        "email": email,
        "password": pwd,
        "office_location_id": 1,
        "role": role
    }, headers=headers)
    assert create_res.status_code == 201
    emp_data = create_res.json()

    # Login to get token
    login_res = client.post("/auth/login", json={"email": email, "password": pwd})
    token = login_res.json()["access_token"]

    return {
        "employee_id": emp_data["id"],
        "email": email,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"}
    }


def test_geofence_check_in_and_check_out():
    user = create_test_employee()

    # 1. Check in outside office radius (approx 7km away)
    far_res = client.post(
        "/attendance/check-in",
        json={"lat": 22.370000, "lng": 73.250000, "method": "mobile_geofence"},
        headers=user["headers"]
    )
    assert far_res.status_code == 400
    assert "from your office. Check-in not allowed" in far_res.json()["detail"]

    # 2. Check in inside office radius (exact Head Office coords: 22.307159, 73.181219)
    in_res = client.post(
        "/attendance/check-in",
        json={"lat": 22.307159, "lng": 73.181219, "method": "mobile_geofence"},
        headers=user["headers"]
    )
    assert in_res.status_code == 200
    data = in_res.json()
    assert data["employee_id"] == user["employee_id"]
    assert data["status"] == "present"
    assert "check_in_time" in data
    att_id = data["id"]

    # 3. Double check in on the same day -> should fail
    dup_res = client.post(
        "/attendance/check-in",
        json={"lat": 22.307159, "lng": 73.181219, "method": "mobile_geofence"},
        headers=user["headers"]
    )
    assert dup_res.status_code == 400
    assert "Already checked in today" in dup_res.json()["detail"]

    # 4. Check out
    out_res = client.post(
        "/attendance/check-out",
        json={"lat": 22.307159, "lng": 73.181219, "method": "mobile_geofence"},
        headers=user["headers"]
    )
    assert out_res.status_code == 200
    out_data = out_res.json()
    assert out_data["id"] == att_id
    assert "check_out_time" in out_data
    assert "total_hours" in out_data

    # 5. Fetch /attendance/me
    me_res = client.get("/attendance/me", headers=user["headers"])
    assert me_res.status_code == 200
    items = me_res.json()["items"]
    assert len(items) >= 1
    assert items[0]["status"] == "present"


def test_regularization_workflow():
    user = create_test_employee()
    admin_token = get_admin_token()
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Check in first
    client.post(
        "/attendance/check-in",
        json={"lat": 22.307159, "lng": 73.181219, "method": "mobile_geofence"},
        headers=user["headers"]
    )

    # Fetch attendance record id
    me_res = client.get("/attendance/me", headers=user["headers"])
    assert len(me_res.json()["items"]) >= 1

    # Employee submits regularization request
    reg_in = {
        "attendance_id": 1,  # or any valid ID
        "requested_check_in": "2026-09-15T09:00:00Z",
        "requested_check_out": "2026-09-15T18:00:00Z",
        "reason": "Forgot to clock out"
    }
    reg_res = client.post("/attendance/regularize", json=reg_in, headers=admin_headers)
    assert reg_res.status_code == 200
    req_id = reg_res.json()["id"]
    assert reg_res.json()["status"] == "pending"

    # Admin approves regularization
    approve_res = client.put(
        f"/attendance/regularize/{req_id}/approve",
        json={"approve": True},
        headers=admin_headers
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "approved"


def test_wfh_request():
    user = create_test_employee()
    wfh_res = client.post(
        "/attendance/wfh-request",
        json={"date": "2026-09-25", "reason": "Client site visit"},
        headers=user["headers"]
    )
    assert wfh_res.status_code == 200
    assert wfh_res.json()["status"] == "wfh_pending_approval"


def test_attendance_excel_export_and_import():
    admin_token = get_admin_token()
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Export Excel
    export_res = client.get("/attendance/export", headers=admin_headers)
    assert export_res.status_code == 200
    assert "spreadsheetml.sheet" in export_res.headers["content-type"]
    assert len(export_res.content) > 0

    # 2. Build a valid test workbook for import
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Employee Code", "Date", "Check In", "Check Out"])
    ws.append(["EMP0001", "2026-09-10", "09:00:00", "18:00:00"])
    excel_stream = io.BytesIO()
    wb.save(excel_stream)
    excel_stream.seek(0)

    # 3. Import Excel
    files = {"file": ("attendance_test.xlsx", excel_stream, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    import_res = client.post("/attendance/import", files=files, headers=admin_headers)
    assert import_res.status_code == 200
    import_data = import_res.json()
    assert import_data["imported"] >= 1
