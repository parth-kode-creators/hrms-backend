import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.core.deps import require_role
from app.models.enums import UserRole
from fastapi import APIRouter, Depends

client = TestClient(app)

# Helper test route to verify RBAC
rbac_test_router = APIRouter(prefix="/test-rbac", tags=["Test RBAC"])

@rbac_test_router.get("/admin-only")
def admin_only_endpoint(user = Depends(require_role([UserRole.super_admin, UserRole.hr_admin]))):
    return {"message": "Welcome Admin", "role": user.role.value}

@rbac_test_router.get("/manager-only")
def manager_only_endpoint(user = Depends(require_role([UserRole.manager]))):
    return {"message": "Welcome Manager", "role": user.role.value}

app.include_router(rbac_test_router)


def test_login_success():
    payload = {
        "email": settings.FIRST_SUPER_ADMIN_EMAIL,
        "password": settings.FIRST_SUPER_ADMIN_PASSWORD
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] if "email" in data["user"] else True
    assert data["user"]["role"] == "super_admin"
    assert data["user"]["full_name"] == settings.FIRST_SUPER_ADMIN_NAME


def test_login_invalid_password():
    payload = {
        "email": settings.FIRST_SUPER_ADMIN_EMAIL,
        "password": "WrongPassword123!"
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_login_nonexistent_email():
    payload = {
        "email": "ghost@company.com",
        "password": "AnyPassword123!"
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_get_current_user_me():
    # Login first
    login_res = client.post("/auth/login", json={
        "email": settings.FIRST_SUPER_ADMIN_EMAIL,
        "password": settings.FIRST_SUPER_ADMIN_PASSWORD
    })
    token = login_res.json()["access_token"]

    # Call /auth/me
    headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get("/auth/me", headers=headers)
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == settings.FIRST_SUPER_ADMIN_EMAIL
    assert me_data["role"] == "super_admin"
    assert me_data["id"] is not None


def test_get_me_without_token():
    res = client.get("/auth/me")
    assert res.status_code in [401, 403]


def test_refresh_token_cycle():
    login_res = client.post("/auth/login", json={
        "email": settings.FIRST_SUPER_ADMIN_EMAIL,
        "password": settings.FIRST_SUPER_ADMIN_PASSWORD
    })
    refresh_tok = login_res.json()["refresh_token"]

    # Request new access token
    refresh_res = client.post("/auth/refresh", json={"refresh_token": refresh_tok})
    assert refresh_res.status_code == 200
    new_access_token = refresh_res.json()["access_token"]
    assert new_access_token is not None

    # Verify new token works on /auth/me
    headers = {"Authorization": f"Bearer {new_access_token}"}
    me_res = client.get("/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == settings.FIRST_SUPER_ADMIN_EMAIL


def test_rbac_middleware_enforcement():
    login_res = client.post("/auth/login", json={
        "email": settings.FIRST_SUPER_ADMIN_EMAIL,
        "password": settings.FIRST_SUPER_ADMIN_PASSWORD
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Super Admin accessing admin-only endpoint -> 200 OK
    admin_res = client.get("/test-rbac/admin-only", headers=headers)
    assert admin_res.status_code == 200
    assert admin_res.json()["role"] == "super_admin"

    # Super Admin accessing manager-only endpoint -> 403 Forbidden
    mgr_res = client.get("/test-rbac/manager-only", headers=headers)
    assert mgr_res.status_code == 403
    assert mgr_res.json()["detail"] == "Operation not permitted"


def test_api_v1_prefix_support():
    # Verify that endpoints work with /api/v1 prefix as well
    payload = {
        "email": settings.FIRST_SUPER_ADMIN_EMAIL,
        "password": settings.FIRST_SUPER_ADMIN_PASSWORD
    }
    res = client.post("/api/v1/auth/login", json=payload)
    assert res.status_code == 200
    token = res.json()["access_token"]

    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == settings.FIRST_SUPER_ADMIN_EMAIL
