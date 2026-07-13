# Analytics data contract

Version `demo_analytics.v1` exports append-only, sanitized facts and aggregates:

- `demo_facts`: pseudonymous demo token, tenant, sufficiently coarse region, UTC date bucket, mode, requirement categories, lifecycle durations, scheduled/completed/no-show/conversion flags, quality rubric scores, model/policy versions.
- `regional_metric_snapshots`: window, region, eligible sample size, numerator/denominator, estimate, interval, baseline, practical difference, suppression status.
- `provider_cost_facts`: provider/operation/date, calls, tokens/units, latency/error buckets, configured currency cost; no user identifier.

Forbidden: raw phone/email, names, addresses/pincodes at re-identifying granularity, message/evidence text, meeting/calendar links, child detail, provider/payment payload, access token, account/card/bank data, free-form admin notes, and cohorts below the approved suppression threshold.

Exports include `schema_version`, `exported_at`, `source_snapshot_at`, `classification`, `producer_version`, and deterministic event key. Glue tables are partitioned by UTC date/environment. Contract changes are additive within v1; semantic/removal changes require v2 and dual-publish validation. Athena access is read-only, environment/role scoped, logged, and excludes operational KMS decrypt permissions.
