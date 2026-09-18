import uuid
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


def create_test_employee() -> dict:
    admin_token = get_admin_token()
    headers = {"Authorization": f"Bearer {admin_token}"}
    uid = uuid.uuid4().hex[:6]
    email = f"holiday.user.{uid}@company.com"
    pwd = "Password123!"

    create_res = client.post("/employees", json={
        "full_name": f"Holiday Tester {uid}",
        "email": email,
        "password": pwd,
        "role": "employee"
    }, headers=headers)
    assert create_res.status_code == 201

    login_res = client.post("/auth/login", json={"email": email, "password": pwd})
    token = login_res.json()["access_token"]

    return {
        "employee_id": create_res.json()["id"],
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"}
    }


def test_holiday_crud_and_optional_selection():
    admin_token = get_admin_token()
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    uid = uuid.uuid4().hex[:6]

    # 1. Create a festival holiday
    fest_in = {
        "name": f"Diwali {uid}",
        "date": "2026-11-08",
        "type": "festival",
        "year": 2026,
        "description": "Festival of Lights"
    }
    fest_res = client.post("/holidays", json=fest_in, headers=admin_headers)
    assert fest_res.status_code == 201
    assert fest_res.json()["name"] == f"Diwali {uid}"

    # 2. Create 3 optional holidays to test the cap of 2
    opt_ids = []
    for i in range(1, 4):
        opt_in = {
            "name": f"Optional Holiday {i} {uid}",
            "date": f"2026-03-0{i}",
            "type": "optional",
            "year": 2026,
            "description": "Floating holiday"
        }
        opt_res = client.post("/holidays", json=opt_in, headers=admin_headers)
        assert opt_res.status_code == 201
        opt_ids.append(opt_res.json()["id"])

    # 3. List holidays for 2026
    list_res = client.get("/holidays?year=2026", headers=admin_headers)
    assert list_res.status_code == 200
    holidays = list_res.json()["items"]
    assert len(holidays) >= 4

    # 4. Employee selects 1st optional holiday -> 200 OK
    user = create_test_employee()
    sel1 = client.post(f"/holidays/{opt_ids[0]}/select-optional", headers=user["headers"])
    assert sel1.status_code == 200
    assert sel1.json()["holiday_id"] == opt_ids[0]

    # 5. Selecting same holiday again -> 400 Bad Request
    dup_sel = client.post(f"/holidays/{opt_ids[0]}/select-optional", headers=user["headers"])
    assert dup_sel.status_code == 400

    # 6. Selecting 2nd optional holiday -> 200 OK (reaches cap of 2)
    sel2 = client.post(f"/holidays/{opt_ids[1]}/select-optional", headers=user["headers"])
    assert sel2.status_code == 200

    # 7. Selecting 3rd optional holiday -> 400 Bad Request (exceeds cap)
    sel3 = client.post(f"/holidays/{opt_ids[2]}/select-optional", headers=user["headers"])
    assert sel3.status_code == 400
    assert "maximum allowed optional holidays" in sel3.json()["detail"]
