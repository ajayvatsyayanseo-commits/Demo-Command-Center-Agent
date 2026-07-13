# Transition registry ownership

`table.py` intentionally keeps the complete declarative demo-state registry in one auditable location, even though the declaration is slightly over the normal 400-line target. Splitting by capability would make completeness, conflicting commands, and terminal-state review harder. It contains typed data declarations and lookup validation rather than orchestration logic; future implementation may generate the registry from a versioned state contract if that preserves one-source completeness.
