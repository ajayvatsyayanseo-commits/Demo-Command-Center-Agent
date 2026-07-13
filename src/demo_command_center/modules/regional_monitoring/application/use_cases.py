from __future__ import annotations

from dataclasses import dataclass

from demo_command_center.modules.regional_monitoring.domain.policy import (
    PrincipalScope,
    RegionalAuthorizationPolicy,
    ScopeDecision,
    ScopeRequest,
    authorize_scope,
)


@dataclass(frozen=True, slots=True)
class RegionalAuthorizationUseCase:
    policy: RegionalAuthorizationPolicy

    def execute(self, principal: PrincipalScope, request: ScopeRequest) -> ScopeDecision:
        return authorize_scope(principal, request, self.policy)
