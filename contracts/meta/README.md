# Meta contract boundary

Lead Intake owns Meta payload schemas and version drift. Demo Command Center accepts only canonical agent events, never an unvalidated Meta object. Any emergency direct boundary must verify the untouched raw body, app secret signature, content size/type, and durable provider event ID before returning success; it is disabled in the scaffold.
