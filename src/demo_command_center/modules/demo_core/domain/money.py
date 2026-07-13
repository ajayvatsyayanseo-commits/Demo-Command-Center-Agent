from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, order=True)
class Money:
    """Integer-minor-unit money with an explicit currency boundary."""

    amount_minor: int
    currency: str

    def __post_init__(self) -> None:
        normalized = self.currency.strip().upper()
        if self.amount_minor < 0:
            raise ValueError("money cannot be negative")
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("currency must be a three-letter ISO code")
        object.__setattr__(self, "currency", normalized)

    def require_same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise ValueError("currency mismatch")

    def subtract(self, other: Money) -> Money:
        self.require_same_currency(other)
        if other.amount_minor > self.amount_minor:
            raise ValueError("money subtraction cannot be negative")
        return Money(self.amount_minor - other.amount_minor, self.currency)

    def discounted_by_basis_points(self, basis_points: int) -> Money:
        if not 0 <= basis_points <= 10_000:
            raise ValueError("basis points must be between zero and 10000")
        # Round towards the customer charge (up) so a policy floor is never crossed.
        numerator = self.amount_minor * (10_000 - basis_points)
        return Money((numerator + 9_999) // 10_000, self.currency)
