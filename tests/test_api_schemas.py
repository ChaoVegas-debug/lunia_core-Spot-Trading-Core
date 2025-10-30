import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lunia_core.app.services.api.schemas import (
    FuturesTradeRequest,
    SignalPayload,
    TradeRequest,
)


def test_trade_request_requires_symbol():
    with pytest.raises(ValueError, match="symbol field required"):
        TradeRequest.parse_obj({"side": "buy", "qty": 1})


def test_trade_request_normalizes_fields():
    req = TradeRequest.parse_obj({"symbol": "ethusdt", "side": "sell", "qty": 1})
    assert req.symbol == "ETHUSDT"
    assert req.side == "SELL"
    assert req.qty == 1


def test_trade_request_rejects_blank_symbol():
    with pytest.raises(ValueError, match="symbol field required"):
        TradeRequest.parse_obj({"symbol": "", "side": "buy", "qty": 1})


def test_futures_trade_request_normalizes_type():
    req = FuturesTradeRequest.parse_obj({"symbol": "ethusdt", "side": "buy", "qty": 1, "type": "limit"})
    assert req.symbol == "ETHUSDT"
    assert req.side == "BUY"
    assert req.type == "LIMIT"


def test_signal_payload_requires_symbol():
    with pytest.raises(ValueError, match="symbol field required"):
        SignalPayload.parse_obj({"side": "buy", "qty": 1})


def test_signal_payload_normalizes_symbol():
    payload = SignalPayload.parse_obj({"symbol": "bnbusdt", "side": "sell", "qty": 2})
    assert payload.symbol == "BNBUSDT"
    assert payload.side == "SELL"
    assert payload.qty == 2
