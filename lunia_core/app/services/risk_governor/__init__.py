"""
Risk Governor — Portfolio Safety Enforcement Layer

Epoch C.2: Position & Exposure Governor (Iron Dome v1.0)

Pre-execution risk enforcement:
- Hard limits: BLOCK orders that violate caps
- Soft limits: MANUAL_REVIEW or downgrade
- Circuit breaker: Halt recommendation
- Journal: All decisions auditable
"""
