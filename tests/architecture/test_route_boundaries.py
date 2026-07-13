from fastapi.routing import APIRoute

from demo_command_center.bootstrap.application_factory import create_application
from demo_command_center.config.settings import Settings


def test_internal_routes_have_authentication_dependency() -> None:
    app = create_application(Settings(app_env="test", _env_file=None))
    internal = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/v1/internal/")
    ]
    assert internal
    assert all(route.dependencies for route in internal)


def test_only_declared_public_boundaries_are_mounted() -> None:
    app = create_application(Settings(app_env="test", _env_file=None))
    paths = {route.path for route in app.routes if isinstance(route, APIRoute)}
    allowed_prefixes = ("/health/", "/v1/internal/", "/v1/provider/")
    assert all(path.startswith(allowed_prefixes) for path in paths)


def test_production_does_not_mount_interactive_or_openapi_documentation() -> None:
    app = create_application(
        Settings(
            app_env="prod",
            provider_profile="real",
            tenant_id="tenant-test",
            database_url="postgresql+asyncpg://configured-reference",
            redis_url="rediss://configured-reference",
            aws_region="configured-region",
            lead_intake_shared_secret="test-only-secret",
            public_base_url="https://public.invalid",
            internal_base_url="https://internal.invalid",
            _env_file=None,
        )
    )
    paths = {getattr(route, "path", "") for route in app.routes}
    assert "/docs" not in paths
    assert "/openapi.json" not in paths
