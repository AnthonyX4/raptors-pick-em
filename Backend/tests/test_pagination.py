import pytest

from config import settings
from conftest import register_and_login

# the admin users list is the only paginated endpoint so far, the games, picks and chat steps add theirs here


@pytest.fixture
def users(client, admin_headers):
    """The admin plus four more users, enough to split across pages with a small limit. Returns their emails in id order."""
    emails = ["admin@example.com"]
    for i in range(4):
        email = f"fan{i}@example.com"
        register_and_login(client, email)
        emails.append(email)
    return emails


def collect_pages(client, path: str, key: str, limit: int, headers: dict | None = None) -> list[dict]:
    """Walk every page of a paginated endpoint by following has_more, returns every row in order."""
    rows, skip = [], 0
    while True:
        page = client.get(path, params={"skip": skip, "limit": limit}, headers=headers).json()
        rows += page[key]
        if not page["has_more"]:
            return rows
        skip += limit


def test_page_reports_total_and_has_more(client, admin_headers, users):
    response = client.get("/api/admin/users", params={"skip": 0, "limit": 2}, headers=admin_headers)
    assert response.status_code == 200
    page = response.json()
    assert [u["email"] for u in page["users"]] == users[:2]
    assert page["total"] == 5
    assert page["skip"] == 0
    assert page["limit"] == 2
    assert page["has_more"] is True


def test_last_page_has_no_more(client, admin_headers, users):
    page = client.get("/api/admin/users", params={"skip": 4, "limit": 2}, headers=admin_headers).json()
    assert [u["email"] for u in page["users"]] == users[4:]
    assert page["has_more"] is False


def test_pages_cover_every_user_once(client, admin_headers, users):
    rows = collect_pages(client, "/api/admin/users", "users", limit=2, headers=admin_headers)
    assert [u["email"] for u in rows] == users


def test_skip_past_the_end_is_an_empty_page(client, admin_headers, users):
    page = client.get("/api/admin/users", params={"skip": 50}, headers=admin_headers).json()
    assert page["users"] == []
    assert page["total"] == 5
    assert page["has_more"] is False


def test_default_limit_comes_from_settings(client, admin_headers):
    assert client.get("/api/admin/users", headers=admin_headers).json()["limit"] == settings.items_per_page


@pytest.mark.parametrize("params", [{"skip": -1}, {"limit": 0}, {"limit": settings.max_page_size + 1}])
def test_out_of_range_params_are_422(client, admin_headers, params):
    assert client.get("/api/admin/users", params=params, headers=admin_headers).status_code == 422


def test_total_counts_rows_beyond_the_page(client, admin_headers, user_headers):
    page = client.get("/api/admin/users", params={"limit": 1}, headers=admin_headers).json()
    assert page["total"] == 2 # the admin and the customer
    assert len(page["users"]) == 1
    assert page["has_more"] is True
