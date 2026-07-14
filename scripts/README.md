# Scripts

Scripts validate contracts or orchestrate documented development checks. Mutating production operations belong in authenticated CLI commands/runbooks.

`production_check.py` is the cross-platform evidence orchestrator. It runs the locked Python quality suite, contracts, workflow and hygiene policies, migration rendering, Terraform checks, the Laravel adapter suite, a container build, repository secret scanning, an optional ephemeral PostgreSQL migration round-trip, and an optional deployed health smoke test.

Run the strict release-evidence check with:

```text
python scripts/production_check.py
```

Exit codes are intentionally distinct:

- `0`: every gate passed, or skips were explicitly accepted with `--allow-skips` and the summary says `PARTIAL`.
- `1`: one or more gates failed.
- `2`: completed gates passed, but release evidence is incomplete because one or more gates were skipped.

The runner never loads `.env`. A database round-trip requires both a loopback test database in `PRODUCTION_CHECK_POSTGRES_URL` and `--allow-database-mutation`. A deployed smoke test uses `PRODUCTION_CHECK_SMOKE_BASE_URL`; it accepts HTTPS, or HTTP only for a loopback service. `make production-check-local` is developer convenience and is not production approval.
