from __future__ import annotations

from typing import Any

from mangum.types import LambdaCognitoIdentity, LambdaMobileClientContext

from demo_command_center.bootstrap.application_factory import create_application
from demo_command_center.config.settings import Settings
from demo_command_center.lambda_handler import build_lambda_handler


class _LambdaContext:
    function_name = "demo-command-center-test"
    function_version = "$LATEST"
    invoked_function_arn = (
        "arn:aws:lambda:ap-south-1:123456789012:function:demo-command-center-test"
    )
    memory_limit_in_mb = 512
    aws_request_id = "pytest-request"
    log_group_name = "/aws/lambda/demo-command-center-test"
    log_stream_name = "pytest"
    client_context: LambdaMobileClientContext | None = None
    identity: LambdaCognitoIdentity | None = None

    def get_remaining_time_in_millis(self) -> int:
        return 30_000


def _http_v2_event(path: str) -> dict[str, Any]:
    return {
        "version": "2.0",
        "routeKey": f"GET {path}",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {
            "accept": "application/json",
            "host": "testserver",
            "user-agent": "pytest",
        },
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "pytest",
            "domainName": "testserver",
            "domainPrefix": "testserver",
            "http": {
                "method": "GET",
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "pytest",
            },
            "requestId": "pytest-request",
            "routeKey": f"GET {path}",
            "stage": "$default",
            "time": "14/Jul/2026:00:00:00 +0000",
            "timeEpoch": 1_784_102_400_000,
        },
        "isBase64Encoded": False,
    }


def test_lambda_http_handler_serves_live_health() -> None:
    app = create_application(
        Settings(app_env="test", provider_profile="local", allowed_hosts=["testserver"])
    )
    lambda_handler = build_lambda_handler(app)

    response = lambda_handler(_http_v2_event("/health/live"), _LambdaContext())

    assert response["statusCode"] == 200
    assert response["headers"]["content-type"] == "application/json"
