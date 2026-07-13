from typing import cast

from fastapi import Request

from demo_command_center.bootstrap.dependency_container import DependencyContainer


def get_container(request: Request) -> DependencyContainer:
    return cast(DependencyContainer, request.app.state.container)
