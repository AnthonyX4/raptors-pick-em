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


def test_user_detail_shows_that_user(client, admin_headers, user_headers):
    me = client.get("/api/users/me", headers=user_headers).json()

    response = client.get(f"/api/admin/users/{me['user_id']}", headers=admin_headers)
    assert response.status_code == 200
    detail = response.json()
    assert detail["email"] == "customer@example.com"
    assert detail["is_admin"] is False


def test_user_detail_missing_user_is_404(client, admin_headers):
    response = client.get("/api/admin/users/999", headers=admin_headers)
    assert response.status_code == 404


# --- deleting users ---

def test_delete_user_removes_the_row(client, admin_headers, user_headers):
    me = client.get("/api/users/me", headers=user_headers).json()

    assert client.delete(f"/api/admin/users/{me['user_id']}", headers=admin_headers).status_code == 204
    assert client.get(f"/api/admin/users/{me['user_id']}", headers=admin_headers).status_code == 404
    assert client.get("/api/users/me", headers=user_headers).status_code == 401 # their token stops working


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


def test_deleting_the_same_user_twice_is_404(client, admin_headers, user_headers):
    me = client.get("/api/users/me", headers=user_headers).json()
    assert client.delete(f"/api/admin/users/{me['user_id']}", headers=admin_headers).status_code == 204

    assert client.delete(f"/api/admin/users/{me['user_id']}", headers=admin_headers).status_code == 404


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
