from __future__ import annotations

import json

import httpx
import pytest

from demo_command_center.integrations.http_security import InternalRequestSigner
from demo_command_center.integrations.nxtutors_website import NxtutorsWebsiteGateway
from demo_command_center.modules.demo_core.ports.gateways import TutorSearchQuery


def _signer() -> InternalRequestSigner:
    return InternalRequestSigner(
        key_id="test-key",
        secret="test-secret",
        source="demo-command-center",
        issuer="nxtutors-internal",
        audience="nxtutors-website-gateway",
    )


@pytest.mark.asyncio
async def test_website_gateway_resolves_purpose_bound_phone_recipients_without_raw_phone() -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = json.loads(request.content)
        assert body["demo_ref"] == "demo-0001"
        assert request.headers["X-NXTutors-Scopes"] in {
            "demo:tutor-phone:read",
            "demo:profile-phone:read",
        }
        if request.url.path.endswith("/tutors/2/phone-resolve"):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "tutor_ref": "2",
                        "user_ref": "teacher-1",
                        "recipient_ref": "register:2:phone",
                        "phone_reference": "register:2:phone",
                        "channel": "whatsapp",
                        "purpose": body["purpose"],
                        "demo_ref": body["demo_ref"],
                        "masked_phone": "*********0002",
                        "source_version": "version-2",
                    }
                },
            )
        return httpx.Response(
            200,
            json={
                "data": {
                    "register_ref": "1",
                    "user_ref": "student-1",
                    "recipient_ref": "register:1:phone",
                    "phone_reference": "register:1:phone",
                    "channel": "whatsapp",
                    "purpose": body["purpose"],
                    "demo_ref": body["demo_ref"],
                    "masked_phone": "*********0001",
                    "source_version": "version-1",
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    gateway = NxtutorsWebsiteGateway(
        base_url="https://website.invalid",
        signer=_signer(),
        timeout_seconds=2,
        client=client,
    )

    tutor = await gateway.resolve_tutor_phone_recipient(
        "2", demo_ref="demo-0001", purpose="demo_tutor_acceptance"
    )
    learner = await gateway.resolve_profile_phone_recipient(
        "1", demo_ref="demo-0001", purpose="demo_session_link"
    )

    assert tutor.recipient_ref == "register:2:phone"
    assert learner.recipient_ref == "register:1:phone"
    assert all("+919" not in request.content.decode() for request in requests)
    await client.aclose()


@pytest.mark.asyncio
async def test_website_gateway_reads_paginated_candidate_items() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/tutors/candidates")
        assert request.headers["X-NXTutors-Scopes"] == "demo:tutors:read"
        return httpx.Response(
            200,
            json={
                "data": {
                    "items": [
                        {
                            "tutor_ref": "2",
                            "display_name": "Tutor Two",
                            "availability_status": "unknown",
                            "source_version": "version-2",
                        }
                    ],
                    "page": 1,
                    "per_page": 20,
                    "has_more": False,
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    gateway = NxtutorsWebsiteGateway(
        base_url="https://website.invalid",
        signer=_signer(),
        timeout_seconds=2,
        client=client,
    )

    candidates = await gateway.search_tutor_candidates(
        TutorSearchQuery(subject="Mathematics", class_level="Class 10", city="Gurugram")
    )

    assert candidates[0]["tutor_ref"] == "2"
    await client.aclose()
