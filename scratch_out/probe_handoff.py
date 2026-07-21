"""Read-only auth probe: sign a handoff exactly like Lead Intake does and POST it
to the live DCC ALB with an intentionally-invalid body ({}).

- 403  -> inbound auth is BROKEN (grant scope mismatch) — demo pipeline can't start
- 422  -> auth PASSED, only body validation failed (no side effect) => FIXED
"""
import sys, os, urllib.request, urllib.error

sys.path.insert(0, "src")
from demo_command_center.integrations.http_security import InternalRequestSigner

ALB = "http://dcc-dev-alb-224383117.ap-south-1.elb.amazonaws.com"
PATH = "/v1/internal/whatsapp/handoffs"

# read the shared secret from AWS Secrets Manager (matches deployed grant)
import subprocess, os
secret = subprocess.check_output(
    ["aws", "secretsmanager", "get-secret-value",
     "--secret-id", "/nxtutors/demo-command-center/dev/lead-intake-shared-secret",
     "--query", "SecretString", "--output", "text"],
    env=dict(os.environ, AWS_PAGER="", MSYS_NO_PATHCONV="1"),
).decode().strip()
assert secret, "lead-intake-shared-secret is empty"

signer = InternalRequestSigner(
    key_id="dev-key",
    secret=secret,
    source="lead-intake-agent",
    issuer="nxtutors-internal",
    audience="demo-command-center",
)
body = b"{}"  # invalid handoff on purpose -> 422 if auth passes, no side effect
headers = signer.headers(method="POST", path=PATH, body=body, scopes=("handoffs:write",))

req = urllib.request.Request(ALB + PATH, data=body, headers=headers, method="POST")
try:
    resp = urllib.request.urlopen(req, timeout=15)
    print("HTTP", resp.status, resp.read().decode()[:300])
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read().decode()[:300])
