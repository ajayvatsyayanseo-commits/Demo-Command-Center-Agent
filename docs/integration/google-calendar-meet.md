# Google Calendar and Meet

An NXTutors-controlled organizer calendar is authoritative for demo events. Configuration identifies the calendar, delegated organizational user/auth mode, credential secret ARN, allowed scopes, and Meet feature gate. No key file is stored in the image/repository.

Creation algorithm:

1. Persist a unique operation and conference request ID derived from demo/session version.
2. Resolve the selected teacher's purpose-bound WhatsApp recipient reference through the Laravel gateway and ask the teacher to accept the proposed slot through Lead Intake.
3. Recheck authoritative hold, tutor acceptance evidence, and Calendar free/busy.
4. Insert with `conferenceDataVersion=1`, attendee policy, private extended `demo_id`/operation ID, and privacy-safe summary.
5. On timeout, query by external property/operation before retry.
6. Persist provider event ID/etag/status and encrypted Meet URI separately.
7. If conference data is pending, poll through durable scheduled work with a bound retry budget and do not send an empty link.
8. Resolve tutor and student/guardian phone recipient references and request WhatsApp delivery only after a usable Meet URI is available.

Reschedule updates the canonical event with etag/concurrency checks when safe; replacement creation is a saga. Cancellation records intent/result and never treats a local status as proof of provider cancellation. External attendee addresses come from authoritative references and are not revealed to other participants unless product policy allows it.

Calendar event content is minimal; child data and phone numbers are excluded. Meeting links are encrypted, never exported/logged, and deleted according to meeting-retention policy.
