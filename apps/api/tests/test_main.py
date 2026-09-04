from fastapi.testclient import TestClient

from relaydesk.main import app

client = TestClient(app)


def test_api_info() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"name": "Relaydesk API", "version": "0.1.0"}


def test_health() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_an_unexpected_exception_returns_the_error_envelope() -> None:
    """Without a catch-all handler this escapes as Starlette's plain-text
    "Internal Server Error", which the web client's `error.code` parsing
    cannot read."""

    @app.get("/api/_explode")
    async def explode() -> None:
        raise RuntimeError("connection string postgres://user:hunter2@db")

    try:
        with TestClient(app, raise_server_exceptions=False) as probe:
            response = probe.get("/api/_explode")
    finally:
        app.router.routes = [
            route
            for route in app.router.routes
            if getattr(route, "path", None) != "/api/_explode"
        ]

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "error"
    assert response.json()["error"]["message"]
    # No exception text, no traceback.
    assert "hunter2" not in response.text
    assert "RuntimeError" not in response.text
    assert "Traceback" not in response.text
