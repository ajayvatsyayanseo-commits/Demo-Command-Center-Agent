# Consent model

Consent records bind canonical participant, guardian relationship where applicable, purpose/channel, affirmative action/evidence hash, policy/text version and URLs, locale, source, UTC granted/withdrawn time, expiry where applicable, and collector flow version.

Purposes are separate: WhatsApp service communication, marketing follow-up, learner email, tutor/learner calendar invitation, recording/transcription, analytics/model training beyond legitimate operations, and approved social proof. Consent is not inferred from silence or bundled across unrelated purposes. Operational messages still respect legal basis and opt-out rules.

STOP/UNSUBSCRIBE creates an immediate durable `opt_out_record`, cancels pending prohibited deliveries, and propagates to the outbound owner. Withdrawal does not erase lawful historical evidence but prevents future purpose use. Child participation requires verified guardian policy and minimizes child identity. Recording/transcription is disabled until explicit consent is recorded for all required participants.
