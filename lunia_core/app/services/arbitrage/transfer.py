"""Transfer and routing helpers for arbitrage execution."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict


@dataclass
class TransferResult:
    """Outcome of a simulated transfer step."""

    method: str
    fee_usd: float
    eta_sec: float
    success: bool
    message: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "method": self.method,
            "fee_usd": round(self.fee_usd, 6),
            "eta_sec": self.eta_sec,
            "success": self.success,
            "message": self.message,
        }


def internal_transfer(from_exchange: str, to_exchange: str, symbol: str, qty: float) -> TransferResult:
    eta = 5.0
    message = (
        f"internal transfer {symbol} qty={qty:.6f} {from_exchange}->{to_exchange}"
    )
    return TransferResult(method="internal", fee_usd=0.0, eta_sec=eta, success=True, message=message)


def withdraw_and_deposit(
    from_exchange: str,
    to_exchange: str,
    symbol: str,
    qty: float,
    fee_usd: float,
    eta_sec: float,
) -> TransferResult:
    message = (
        f"chain transfer {symbol} qty={qty:.6f} {from_exchange}->{to_exchange} fee={fee_usd:.2f}"
    )
    return TransferResult(method="chain", fee_usd=fee_usd, eta_sec=eta_sec, success=True, message=message)


def convert_if_needed(symbol_from: str, symbol_to: str) -> Dict[str, object]:
    if symbol_from == symbol_to:
        return {"converted": False, "path": [symbol_from]}
    path = [symbol_from, "USDC", symbol_to]
    return {"converted": True, "path": path, "timestamp": time.time()}


__all__ = [
    "TransferResult",
    "internal_transfer",
    "withdraw_and_deposit",
    "convert_if_needed",
]
