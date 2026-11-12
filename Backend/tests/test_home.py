from config import settings


def test_home_reports_the_api_is_running(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": f"{settings.app_name} API is running"}
