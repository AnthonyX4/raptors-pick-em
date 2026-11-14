from config import settings


def test_home_reports_the_api_is_running(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": f"{settings.app_name} API is running"}


def test_health_runs_a_query(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_health_is_503_when_the_database_is_unreachable(client):
    import database
    import main

    class BrokenSession:
        async def execute(self, *args):
            raise ConnectionError("database is gone")

    async def broken_db():
        yield BrokenSession()

    main.app.dependency_overrides[database.get_db] = broken_db # the client fixture resets overrides after the test
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}


def test_every_response_carries_the_security_headers(client):
    for response in (client.get("/"), client.get("/api/games/nope")): # a 404 gets them too
        assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert response.headers["Strict-Transport-Security"].startswith("max-age=")


def test_no_hsts_on_a_local_dev_server(db): # db: the app checks its tables exist on startup
    from fastapi.testclient import TestClient
    import main

    with TestClient(main.app, base_url="http://localhost") as local:
        assert "Strict-Transport-Security" not in local.get("/").headers
