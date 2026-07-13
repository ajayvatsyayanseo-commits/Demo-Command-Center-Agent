# API documentation ownership

Versioned machine contracts live under `contracts/openapi/`; route implementation lives under `src/demo_command_center/api/`. A contract change requires compatibility review, schema validation, generated-client impact review, and an ADR when it changes service ownership. Provider callbacks are not general public APIs and remain fail-closed until signature, replay, size, and content-type controls are configured.
