from demo_command_center.api.routes.health import router as health_router
from demo_command_center.api.routes.internal import router as internal_router
from demo_command_center.api.routes.providers import router as provider_router

__all__ = ["health_router", "internal_router", "provider_router"]
