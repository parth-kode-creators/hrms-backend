import io
import uuid
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


def create_test_employee(manager_id: int = None) -> dict:
    admin_token = get_admin_token()
    headers = {"Authorization": f"Bearer {admin_token}"}
    uid = uuid.uuid4().hex[:6]
    email = f"leave.user.{uid}@company.com"
    pwd = "Password123!"

    payload = {
        "full_name": f"Leave Tester {uid}",
        "email": email,
        "password": pwd,
        "department_id": 2,
        "office_location_id": 1,
        "role": "employee"
    }
    if manager_id:
        payload["manager_id"] = manager_id

    create_res = client.post("/employees", json=payload, headers=headers)
    assert create_res.status_code == 201
    emp_data = create_res.json()

    login_res = client.post("/auth/login", json={"email": email, "password": pwd})
    token = login_res.json()["access_token"]

    return {
        "employee_id": emp_data["id"],
        "email": email,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"}
    }


def test_get_leave_types():
    admin_token = get_admin_token()
    headers = {"Authorization": f"Bearer {admin_token}"}

    res = client.get("/leave-types", headers=headers)
    assert res.status_code == 200
    types = res.json()["items"]
    type_names = [t["name"] for t in types]
    assert "Casual" in type_names
    assert "Sick" in type_names
    assert "Privilege" in type_names


def test_leave_balances_and_apply_flow():
    user = create_test_employee()

    # 1. Check initial balances
    bal_res = client.get("/leave/balance/me", headers=user["headers"])
    assert bal_res.status_code == 200
    balances = bal_res.json()["items"]
    assert len(balances) >= 3
    casual_bal = next(b for b in balances if b["leave_type"] == "Casual")
    assert casual_bal["total_allotted"] == 12.0
    assert casual_bal["used"] == 0.0
    assert casual_bal["balance"] == 12.0

    # 2. Apply for 2 days leave on Monday-Tuesday (2026-10-05 to 2026-10-06)
    # Find Casual leave_type_id
    types_res = client.get("/leave-types", headers=user["headers"])
    casual_id = next(t["id"] for t in types_res.json()["items"] if t["name"] == "Casual")

    apply_payload = {
        "leave_type_id": casual_id,
        "start_date": "2026-10-05",
        "end_date": "2026-10-06",
        "is_half_day": False,
        "reason": "Family trip"
    }
    apply_res = client.post("/leave/apply", json=apply_payload, headers=user["headers"])
    assert apply_res.status_code == 201
    app_data = apply_res.json()
    assert app_data["status"] == "pending"
    leave_id = app_data["id"]

    # 3. Test applying for excessive days exceeding balance
    excess_payload = {
        "leave_type_id": casual_id,
        "start_date": "2026-11-02",
        "end_date": "2026-11-27",  # ~20 working days
        "is_half_day": False,
        "reason": "Long break"
    }
    excess_res = client.post("/leave/apply", json=excess_payload, headers=user["headers"])
    assert excess_res.status_code == 400
    assert "Insufficient Casual leave balance" in excess_res.json()["detail"]

    # 4. Admin approves leave request
    admin_token = get_admin_token()
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    approve_res = client.put(f"/leave/{leave_id}/approve", headers=admin_headers)
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "approved"

    # 5. Verify that balance was deducted (12 allotted - 2 used = 10 remaining)
    bal_after = client.get("/leave/balance/me", headers=user["headers"]).json()["items"]
    casual_after = next(b for b in bal_after if b["leave_type"] == "Casual")
    assert casual_after["used"] == 2.0
    assert casual_after["balance"] == 10.0


def test_reject_leave_flow():
    user = create_test_employee()
    admin_token = get_admin_token()
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    types_res = client.get("/leave-types", headers=user["headers"])
    sick_id = next(t["id"] for t in types_res.json()["items"] if t["name"] == "Sick")

    # Apply for 1 day leave
    apply_payload = {
        "leave_type_id": sick_id,
        "start_date": "2026-10-12",
        "end_date": "2026-10-12",
        "is_half_day": False,
        "reason": "Doctor appointment"
    }
    apply_res = client.post("/leave/apply", json=apply_payload, headers=user["headers"])
    assert apply_res.status_code == 201
    leave_id = apply_res.json()["id"]

    # Reject leave
    reject_payload = {"comment": "Critical sprint deadline"}
    reject_res = client.put(f"/leave/{leave_id}/reject", json=reject_payload, headers=admin_headers)
    assert reject_res.status_code == 200
    assert reject_res.json()["status"] == "rejected"

    # Verify balance was NOT deducted
    bal_after = client.get("/leave/balance/me", headers=user["headers"]).json()["items"]
    sick_after = next(b for b in bal_after if b["leave_type"] == "Sick")
    assert sick_after["used"] == 0.0
    assert sick_after["balance"] == 8.0


def test_leave_export_and_import():
    admin_token = get_admin_token()
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Export leaves to Excel
    export_res = client.get("/leave/export", headers=admin_headers)
    assert export_res.status_code == 200
    assert "spreadsheetml.sheet" in export_res.headers["content-type"]

    # 2. Build test workbook for importing leave balance adjustment
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Employee Code", "Leave Type", "Year", "Total Allotted"])
    ws.append(["EMP0001", "Casual", 2026, 14.0])
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)

    # 3. Import
    files = {"file": ("leave_test.xlsx", stream, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    import_res = client.post("/leave/import", files=files, headers=admin_headers)
    assert import_res.status_code == 200
    assert import_res.json()["imported"] >= 1
