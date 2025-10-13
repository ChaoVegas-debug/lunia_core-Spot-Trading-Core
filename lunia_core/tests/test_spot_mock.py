from app.core.exchange.binance_spot import BinanceSpot


def test_mock_order_execution(tmp_path, monkeypatch):
    client = BinanceSpot(mock=True)
    order = client.place_order("BTCUSDT", "BUY", 0.01)
    assert order["status"] == "FILLED"
    assert order["symbol"] == "BTCUSDT"
    assert order["side"] == "BUY"
    assert order["executedQty"] == 0.01


def test_mock_balances_and_position():
    client = BinanceSpot(mock=True)
    balances = client.get_balances()
    assert "USDT" in balances
    position = client.get_position("BTCUSDT")
    assert position["symbol"] == "BTCUSDT"
