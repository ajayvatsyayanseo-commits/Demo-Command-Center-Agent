# Identity mapping

`external_identity_mappings` maps a canonical subject (`demo_participant`, `website_user`, `website_tutor`, `lead`, `conversation`) to provider/system namespace and opaque external reference. Raw phone/email are not identifiers in envelopes.

Required fields: tenant, canonical type/ID, external system, external type/ID ciphertext or opaque ID, keyed lookup hash when needed, verification level, source, valid-from/to, last verified time, confidence, and version. Unique active mapping is enforced per external namespace/reference.

Identity resolution order:

1. Authenticated website user/tutor reference.
2. Existing verified external mapping.
3. Lead Intake conversation and hashed provider identity evidence.
4. Deterministic candidate match requiring verification.
5. Human handoff for ambiguity or low confidence.

Mappings never silently merge two accounts. A merge records both prior mappings, evidence, approver, reason, and audit event. Child/guardian relationships are purpose-scoped and minimize child data. Analytics receives a separate rotating pseudonym, not operational IDs or hashes reusable outside analytics.
