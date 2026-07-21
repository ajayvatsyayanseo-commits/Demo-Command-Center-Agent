"""Verify the DCC->Lead Intake outbound auth (mirror of the inbound probe).
Signs exactly like DCC's LeadIntakeOutboundGateway and POSTs an empty body to the
real Lead Intake Lambda. 401/403 = auth broken; 4xx validation = auth OK.
"""
import sys, os, subprocess, urllib.request, urllib.error
sys.path.insert(0, "src")
from demo_command_center.integrations.http_security import InternalRequestSigner

BASE = "https://xhjb3bqfi2tlgm5cpyyhcxcsvi0lhlpj.lambda-url.ap-south-1.on.aws"
PATH = "/v1/internal/outbound/whatsapp"

secret = subprocess.check_output(
    ["aws", "secretsmanager", "get-secret-value",
     "--secret-id", "/nxtutors/demo-command-center/dev/lead-intake-shared-secret",
     "--query", "SecretString", "--output", "text"],
    env=dict(os.environ, AWS_PAGER="", MSYS_NO_PATHCONV="1"),
).decode().strip()

signer = InternalRequestSigner(  # matches DCC LeadIntakeOutboundGateway
    key_id="dev-key", secret=secret, source="demo-command-center-agent",
    issuer="nxtutors-internal", audience="lead-intake-agent",
)
body = b"{}"
headers = signer.headers(method="POST", path=PATH, body=body, scopes=("whatsapp:send",))
req = urllib.request.Request(BASE + PATH, data=body, headers=headers, method="POST")
try:
    r = urllib.request.urlopen(req, timeout=15)
    print("HTTP", r.status, r.read().decode()[:200])
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read().decode()[:200])
