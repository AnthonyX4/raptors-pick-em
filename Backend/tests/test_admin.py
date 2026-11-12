from io import BytesIO

import pytest
from PIL import Image

ADMIN_ROUTES = [
    ("get", "/api/admin/users"),
    ("get", "/api/admin/users/1"),
    ("delete", "/api/admin/users/1"),
]


# --- access control ---

@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_admin_routes_reject_normal_users(client, user_headers, method, path):
    response = client.request(method, path, headers=user_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_admin_routes_reject_missing_token(client, method, path):
    response = client.request(method, path)
    assert response.status_code == 401


# --- viewing users ---

def test_list_users_shows_every_user(client, admin_headers, user_headers):
    response = client.get("/api/admin/users", headers=admin_headers)
    assert response.status_code == 200
    users = response.json()["users"]
    assert [u["email"] for u in users] == ["admin@example.com", "customer@example.com"]
    assert users[0]["is_admin"] is True
    assert users[1]["is_admin"] is False
    assert users[1]["deleted_at"] is None


def test_list_users_includes_soft_deleted_users_unless_filtered(client, admin_headers, user_headers, soft_delete):
    me = client.get("/api/users/me", headers=user_headers).json()
    assert client.delete(f"/api/users/{me['user_id']}", headers=user_headers).status_code == 204

    everyone = client.get("/api/admin/users", headers=admin_headers).json()["users"]
    deleted = next(u for u in everyone if u["user_id"] == me["user_id"])
    assert deleted["deleted_at"] is not None
    assert deleted["email"] == f"deleted-{me['user_id']}@invalid.example"
    assert deleted["username"] == f"[deleted-{me['user_id']}]"

    active = client.get("/api/admin/users", params={"include_deleted": False}, headers=admin_headers).json()["users"]
    assert me["user_id"] not in [u["user_id"] for u in active]


def test_user_detail_shows_that_user(client, admin_headers, user_headers):
    me = client.get("/api/users/me", headers=user_headers).json()

    response = client.get(f"/api/admin/users/{me['user_id']}", headers=admin_headers)
    assert response.status_code == 200
    detail = response.json()
    assert detail["email"] == "customer@example.com"
    assert detail["is_admin"] is False
    assert detail["deleted_at"] is None


def test_user_detail_missing_user_is_404(client, admin_headers):
    response = client.get("/api/admin/users/999", headers=admin_headers)
    assert response.status_code == 404


# --- deleting users ---

def test_delete_user_without_history_is_a_hard_delete(client, admin_headers, user_headers):
    me = client.get("/api/users/me", headers=user_headers).json()

    assert client.delete(f"/api/admin/users/{me['user_id']}", headers=admin_headers).status_code == 204
    assert client.get(f"/api/admin/users/{me['user_id']}", headers=admin_headers).status_code == 404
    assert client.get("/api/users/me", headers=user_headers).status_code == 401 # their token stops working


def test_delete_user_with_history_is_a_soft_delete(client, admin_headers, user_headers, soft_delete):
    me = client.get("/api/users/me", headers=user_headers).json()

    assert client.delete(f"/api/admin/users/{me['user_id']}", headers=admin_headers).status_code == 204

    detail = client.get(f"/api/admin/users/{me['user_id']}", headers=admin_headers).json() # the row is still there
    assert detail["deleted_at"] is not None
    assert detail["email"] == f"deleted-{me['user_id']}@invalid.example"
    assert client.get("/api/users/me", headers=user_headers).status_code == 401


def test_delete_user_removes_their_picture(client, admin_headers, user_headers, s3_bucket):
    me = client.get("/api/users/me", headers=user_headers).json()
    picture = client.patch(
        f"/api/users/{me['user_id']}/picture",
        files={"file": ("pic.png", _png(), "image/png")},
        headers=user_headers,
    )
    assert picture.status_code == 200
    assert len(s3_bucket) == 1

    assert client.delete(f"/api/admin/users/{me['user_id']}", headers=admin_headers).status_code == 204
    assert s3_bucket == {}


def test_delete_missing_user_is_404(client, admin_headers):
    assert client.delete("/api/admin/users/999", headers=admin_headers).status_code == 404


def test_delete_already_deleted_user_is_400(client, admin_headers, user_headers, soft_delete):
    me = client.get("/api/users/me", headers=user_headers).json()
    assert client.delete(f"/api/admin/users/{me['user_id']}", headers=admin_headers).status_code == 204 # soft delete, so the row is still there

    response = client.delete(f"/api/admin/users/{me['user_id']}", headers=admin_headers)
    assert response.status_code == 400
    assert response.json()["detail"] == "User is already deleted"


def test_cannot_delete_an_admin(client, admin_headers):
    # covers both deleting another admin and deleting yourself, admin is only removed through make_admin.py
    admin = client.get("/api/users/me", headers=admin_headers).json()
    response = client.delete(f"/api/admin/users/{admin['user_id']}", headers=admin_headers)
    assert response.status_code == 403
    assert client.get("/api/users/me", headers=admin_headers).status_code == 200


def _png() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (50, 50), "red").save(buffer, "PNG")
    return buffer.getvalue()
