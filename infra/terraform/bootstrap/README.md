# Remote-state bootstrap

This isolated root creates the versioned, KMS-encrypted, public-access-blocked S3 bucket used by the environment backends. Terraform's native S3 lockfile (`use_lockfile = true`) provides state locking; no new DynamoDB lock table is required.

Run this once with an approved break-glass/account-bootstrap identity, then copy the output bucket name into a protected `backend.hcl`. The bootstrap root intentionally starts with local state; move and protect that state according to the account bootstrap procedure. Both the bucket and KMS key use `prevent_destroy`.

No example value is a live account identifier. Do not commit generated state, plans, or populated backend configuration.
