from fastapi import FastAPI
from fastapi.routing import APIRoute

from demo_command_center.bootstrap.application_factory import create_application
from demo_command_center.config.settings import Settings


def _api_routes(app: FastAPI) -> list[APIRoute]:
    """Return effective API routes across eager and lazy router inclusion."""
    routes: list[APIRoute] = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            routes.append(route)
            continue
        effective_contexts = getattr(route, "effective_route_contexts", None)
        if not callable(effective_contexts):
            continue
        routes.extend(
            context.original_route
            for context in effective_contexts()
            if isinstance(context.original_route, APIRoute)
        )
    return routes


def test_internal_routes_have_authentication_dependency() -> None:
    app = create_application(Settings(app_env="test", _env_file=None))
    internal = [
        route
        for route in _api_routes(app)
        if isinstance(route, APIRoute) and route.path.startswith("/v1/internal/")
    ]
    assert internal
    assert all(route.dependencies for route in internal)


def test_only_declared_public_boundaries_are_mounted() -> None:
    app = create_application(Settings(app_env="test", _env_file=None))
    paths = {route.path for route in _api_routes(app)}
    allowed_prefixes = ("/health/", "/v1/internal/", "/v1/provider/")
    assert all(path.startswith(allowed_prefixes) for path in paths)


def test_production_does_not_mount_interactive_or_openapi_documentation() -> None:
    app = create_application(
        Settings(
            app_env="prod",
            provider_profile="real",
            tenant_id="tenant-test",
            database_url="postgresql+asyncpg://configured-reference?ssl=require",
            redis_url="rediss://configured-reference",
            aws_region="configured-region",
            public_base_url="https://public.invalid",
            internal_base_url="https://internal.invalid",
            internal_signing_key_id="test-key-v1",
            internal_hmac_key_grants={
                "test-key-v1": {
                    "secret": "test-only-signing-secret",
                    "source": "lead-intake-agent",
                    "scopes": ["events:read", "events:write", "handoffs:write", "health:read"],
                }
            },
            internal_replay_window_seconds=300,
            internal_legacy_shared_secret_enabled=False,
            field_encryption_key="hex:" + "11" * 32,
            field_encryption_key_reference="test-key-reference",
            audit_hash_key="test-audit-key",
            audit_hash_key_reference="test-audit-key-reference",
            nxtutors_website_internal_base_url="https://website.invalid",
            nxtutors_website_shared_secret="test-website-secret",
            nxtutors_website_timeout_seconds=2,
            _env_file=None,
        )
    )
    paths = {getattr(route, "path", "") for route in app.routes}
    assert "/docs" not in paths
    assert "/openapi.json" not in paths
