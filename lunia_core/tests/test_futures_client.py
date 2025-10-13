from app.core.exchange.binance_futures import BinanceFutures, BinanceFuturesError


def test_mock_order_execution():
    client = BinanceFutures(mock=True)
    order = client.place_order("BTCUSDT", "BUY", 0.1)
    assert order["status"] == "FILLED"
    assert order["symbol"] == "BTCUSDT"
    assert order["side"] == "BUY"


def test_place_order_uses_api_when_available(monkeypatch):
    client = BinanceFutures(api_key="k", api_secret="s", use_testnet=True, mock=False)

    def fake_request(method, path, params=None, signed=False):  # noqa: D401
        assert method == "POST"
        assert path == "/fapi/v1/order"
        assert signed is True
        return {"orderId": 123, "status": "FILLED", "symbol": params["symbol"]}

    monkeypatch.setattr(client, "_request", fake_request)
    order = client.place_order("ETHUSDT", "sell", 0.5)
    assert order["orderId"] == 123
    assert order["status"] == "FILLED"
    assert order["symbol"] == "ETHUSDT"
    assert client.mock is False


def test_price_failure_triggers_mock(monkeypatch):
    client = BinanceFutures(api_key="k", api_secret="s", use_testnet=True, mock=False)

    def failing_request(*args, **kwargs):  # noqa: D401
        raise BinanceFuturesError("boom")

    monkeypatch.setattr(client, "_request", failing_request)
    price = client.get_price("BTCUSDT")
    assert price > 0
    assert client.mock is True
