from fastapi.testclient import TestClient
from pydantic import SecretStr

from demo_command_center.bootstrap.application_factory import create_application
from demo_command_center.config.settings import Settings


def test_health_and_internal_auth_boundary() -> None:
    settings = Settings(
        app_env="test",
        provider_profile="local",
        lead_intake_shared_secret=SecretStr("test-internal-secret"),
        _env_file=None,
    )
    with TestClient(create_application(settings)) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200
        assert client.get("/health/dependencies").status_code == 200
        assert client.post("/v1/internal/events", json={}).status_code == 401


def test_direct_meta_boundary_is_disabled() -> None:
    settings = Settings(app_env="test", provider_profile="local", _env_file=None)
    with TestClient(create_application(settings)) as client:
        response = client.post("/v1/provider/meta/whatsapp", content=b"{}")
        assert response.status_code == 404
