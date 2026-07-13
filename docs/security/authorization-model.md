# Tenant and regional authorization

Website authentication remains authoritative for human identity and current Laravel roles. The integration gateway exchanges an authenticated website session for a short-lived internal assertion containing opaque actor ID, tenant ID, role/scopes, permitted region IDs, issuer, audience, key ID, expiry, and nonce. Demo Command Center validates it and never trusts client-supplied region claims.

`super_admin` receives explicit tenant-wide scopes; it is not implemented as an authorization bypass. `sub_admin` receives only assigned operational scopes and region memberships. Service identities receive operation-specific scopes. Every application command carries an authorization context, and repositories apply tenant plus allowed-region predicates before reads, mutations, exports, and aggregate access. PostgreSQL RLS is deferred until it can be proven to strengthen, rather than duplicate or obscure, these predicates.

Exports require a separate scope, exclude restricted fields, record filters and purpose, and emit an audit event. Override access requires an authorized role, reason, expiry, ticket/correlation reference, and immutable audit evidence. Region membership storage and website permission mapping are `UNVERIFIED`; regional endpoints must stay disabled until the gateway contract and source of membership are approved.

Regional alert evaluation uses configured windows, eligible minimum samples, baseline/control periods, uncertainty or practical-significance thresholds, suppression keys, named ownership, acknowledgement, resolution, and escalation. Sparse data suppresses conclusions rather than labeling a region as underperforming.
