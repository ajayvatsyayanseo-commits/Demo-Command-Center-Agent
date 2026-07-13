from __future__ import annotations

import re
from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_SAFE_CORRELATION_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


class CorrelationMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        headers = MutableHeaders(scope=scope)
        candidate = headers.get("x-correlation-id") or headers.get("x-request-id")
        correlation_id = (
            candidate if candidate and _SAFE_CORRELATION_ID.fullmatch(candidate) else str(uuid4())
        )
        scope.setdefault("state", {})["correlation_id"] = correlation_id

        async def send_with_correlation(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                response_headers["X-Correlation-Id"] = correlation_id
            await send(message)

        await self.app(scope, receive, send_with_correlation)
