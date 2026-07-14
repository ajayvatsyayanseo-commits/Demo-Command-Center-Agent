from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, cast

import boto3
from google.oauth2 import service_account
from googleapiclient.discovery import build  # type: ignore[import-untyped]

from demo_command_center.api.errors.taxonomy import ErrorCode, ServiceError
from demo_command_center.modules.demo_core.domain.identifiers import DemoId, IdempotencyKey
from demo_command_center.modules.demo_core.ports.gateways import CalendarEventResult


def workspace_service_factory(
    *,
    secret_arn: str,
    aws_region: str,
    delegated_user: str,
    scopes: Sequence[str],
) -> Callable[[], Any]:
    if not secret_arn or not aws_region or not delegated_user or not scopes:
        raise ValueError(
            "Google Workspace credential reference, delegation, and scopes are required"
        )

    def create() -> Any:
        secrets = boto3.client("secretsmanager", region_name=aws_region)
        response = secrets.get_secret_value(SecretId=secret_arn)
        raw = response.get("SecretString")
        if not isinstance(raw, str):
            raise RuntimeError("Google credential secret has no string value")
        info = json.loads(raw)
        if not isinstance(info, dict):
            raise RuntimeError("Google credential secret is not an object")
        credentials = service_account.Credentials.from_service_account_info(  # type: ignore[no-untyped-call]
            info,
            scopes=list(scopes),
        ).with_subject(delegated_user)
        return build("calendar", "v3", credentials=credentials, cache_discovery=False)

    return create


class GoogleCalendarGateway:
    def __init__(
        self,
        *,
        calendar_id: str,
        service_factory: Callable[[], Any],
    ) -> None:
        if not calendar_id:
            raise ValueError("NXTutors organizer calendar ID is required")
        self._calendar_id = calendar_id
        self._factory = service_factory
        self._service: Any | None = None
        self._service_lock = asyncio.Lock()

    async def _get_service(self) -> Any:
        async with self._service_lock:
            if self._service is None:
                self._service = await asyncio.to_thread(self._factory)
            return self._service

    async def free_busy(
        self,
        calendar_refs: Sequence[str],
        starts_at: datetime,
        ends_at: datetime,
    ) -> Mapping[str, Sequence[tuple[datetime, datetime]]]:
        if starts_at.tzinfo is None or ends_at.tzinfo is None or ends_at <= starts_at:
            raise ValueError("free/busy window must be timezone-aware and positive")
        service = await self._get_service()
        request_body = {
            "timeMin": starts_at.astimezone(UTC).isoformat(),
            "timeMax": ends_at.astimezone(UTC).isoformat(),
            "items": [{"id": item} for item in dict.fromkeys(calendar_refs)],
        }
        try:
            response = await asyncio.to_thread(service.freebusy().query(body=request_body).execute)
        except Exception as exc:
            raise ServiceError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                "Google Calendar free/busy is temporarily unavailable",
            ) from exc
        calendars = response.get("calendars", {}) if isinstance(response, dict) else {}
        result: dict[str, Sequence[tuple[datetime, datetime]]] = {}
        for calendar_ref in calendar_refs:
            data = calendars.get(calendar_ref, {}) if isinstance(calendars, dict) else {}
            busy = data.get("busy", []) if isinstance(data, dict) else []
            intervals: list[tuple[datetime, datetime]] = []
            if isinstance(busy, list):
                for interval in busy:
                    if isinstance(interval, dict):
                        start = _parse_google_time(interval.get("start"))
                        end = _parse_google_time(interval.get("end"))
                        if start is not None and end is not None and end > start:
                            intervals.append((start, end))
            result[calendar_ref] = intervals
        return result

    async def create_demo_event(
        self,
        demo_id: DemoId,
        starts_at: datetime,
        ends_at: datetime,
        attendee_refs: Sequence[str],
        conference_request_id: str,
        idempotency_key: IdempotencyKey,
    ) -> CalendarEventResult:
        if starts_at.tzinfo is None or ends_at.tzinfo is None or ends_at <= starts_at:
            raise ValueError("calendar event window must be timezone-aware and positive")
        if not conference_request_id:
            raise ValueError("a unique conference request ID is required")
        service = await self._get_service()
        body = {
            "summary": "NXTutors demo session",
            "description": f"Demo reference: {demo_id}",
            "start": {"dateTime": starts_at.isoformat()},
            "end": {"dateTime": ends_at.isoformat()},
            "attendees": [{"email": attendee} for attendee in dict.fromkeys(attendee_refs)],
            "extendedProperties": {
                "private": {
                    "demo_id": str(demo_id),
                    "idempotency_key": str(idempotency_key),
                }
            },
            "conferenceData": {
                "createRequest": {
                    "requestId": conference_request_id,
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
        }
        try:
            response = await asyncio.to_thread(
                service.events()
                .insert(
                    calendarId=self._calendar_id,
                    body=body,
                    conferenceDataVersion=1,
                    sendUpdates="all",
                )
                .execute
            )
        except Exception as exc:
            raise ServiceError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                "Google Calendar event creation requires reconciliation",
            ) from exc
        if not isinstance(response, dict) or not isinstance(response.get("id"), str):
            raise ServiceError(
                ErrorCode.PROVIDER_RESPONSE_INVALID,
                "Google Calendar returned an invalid event",
            )
        conference = response.get("conferenceData", {})
        conference = conference if isinstance(conference, dict) else {}
        status_data = conference.get("createRequest", {})
        status_data = status_data if isinstance(status_data, dict) else {}
        status_value = status_data.get("status", {})
        status_value = status_value if isinstance(status_value, dict) else {}
        entry_points = conference.get("entryPoints", [])
        meeting_uri = None
        if isinstance(entry_points, list):
            for point in entry_points:
                if isinstance(point, dict) and point.get("entryPointType") == "video":
                    uri = point.get("uri")
                    meeting_uri = uri if isinstance(uri, str) else None
                    break
        return CalendarEventResult(
            provider_event_id=cast(str, response["id"]),
            provider_etag=response.get("etag") if isinstance(response.get("etag"), str) else None,
            conference_status=str(status_value.get("statusCode", "pending")),
            meeting_uri=meeting_uri,
        )

    async def cancel_event(self, event_ref: str, idempotency_key: IdempotencyKey) -> None:
        del idempotency_key
        service = await self._get_service()
        try:
            await asyncio.to_thread(
                service.events()
                .delete(calendarId=self._calendar_id, eventId=event_ref, sendUpdates="all")
                .execute
            )
        except Exception as exc:
            raise ServiceError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                "Google Calendar cancellation requires reconciliation",
            ) from exc

    async def find_by_demo_id(self, demo_id: DemoId) -> list[dict[str, Any]]:
        service = await self._get_service()
        try:
            response = await asyncio.to_thread(
                service.events()
                .list(
                    calendarId=self._calendar_id,
                    privateExtendedProperty=f"demo_id={demo_id}",
                    maxResults=10,
                    singleEvents=True,
                )
                .execute
            )
        except Exception as exc:
            raise ServiceError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                "Google Calendar reconciliation is temporarily unavailable",
            ) from exc
        items = response.get("items", []) if isinstance(response, dict) else []
        return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _parse_google_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None
