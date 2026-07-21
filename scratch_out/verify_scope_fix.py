"""Local proof using the EXACT production verifier + signer (app_version ba0b594).
Signs a handoff like Lead Intake, then verifies it against (a) the current broken
grant scope and (b) the fixed grant scope. Same secret both sides.
"""
import sys, asyncio
sys.path.insert(0, "src")
from demo_command_center.integrations.http_security import InternalRequestSigner
from demo_command_center.security.authentication import (
    HmacKeyGrant, HmacRequestVerifier, InMemoryReplayStore,
)

secret = next(l.split("=", 1)[1].strip() for l in open(".env", encoding="utf-8")
              if l.startswith("LEAD_INTAKE_SHARED_SECRET="))

signer = InternalRequestSigner(key_id="dev-key", secret=secret, source="lead-intake-agent",
                               issuer="nxtutors-internal", audience="demo-command-center")
body = b'{"probe":true}'
PATH = "/v1/internal/whatsapp/handoffs"


async def check(grant_scopes):
    verifier = HmacRequestVerifier(
        key_grants={"dev-key": HmacKeyGrant(secret=secret, source="lead-intake-agent",
                                            scopes=frozenset(grant_scopes))},
        issuer="nxtutors-internal", audience="demo-command-center",
        replay_window_seconds=300, replay_store=InMemoryReplayStore(),
    )
    headers = signer.headers(method="POST", path=PATH, body=body, scopes=("handoffs:write",))
    headers = {k.lower(): v for k, v in headers.items()}
    try:
        ident = await verifier.verify(method="POST", path=PATH, body=body, headers=headers,
                                      required_scopes={"handoffs:write"})
        return f"ACCEPTED (source={ident.source})"
    except Exception as e:
        return f"REJECTED -> {type(e).__name__}: {e}"


async def main():
    print("current deployed grant scopes ['demo:handoff:write'] :", await check(["demo:handoff:write"]))
    print("fixed grant scopes         ['handoffs:write']       :", await check(["handoffs:write"]))


asyncio.run(main())
