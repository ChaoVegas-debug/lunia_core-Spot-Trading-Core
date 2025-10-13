from app.services.arbitrage.transfer import (
    convert_if_needed,
    internal_transfer,
    withdraw_and_deposit,
)


def test_internal_transfer():
    result = internal_transfer("binance", "okx", "BTC", 0.5)
    assert result.success is True
    assert result.method == "internal"
    assert "binance" in result.message


def test_chain_transfer():
    result = withdraw_and_deposit("binance", "okx", "BTC", 0.5, fee_usd=1.0, eta_sec=120)
    assert result.success is True
    assert result.method == "chain"
    assert "fee" in result.message


def test_convert_if_needed():
    payload = convert_if_needed("BTC", "ETH")
    assert payload["converted"] is True
    assert payload["path"][0] == "BTC"
