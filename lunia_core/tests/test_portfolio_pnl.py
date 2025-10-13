from app.core.portfolio.portfolio import Portfolio


def test_portfolio_tracks_strategy_and_pnl():
    portfolio = Portfolio()
    pnl = portfolio.update_on_fill(
        "BTCUSDT",
        "BUY",
        0.1,
        100.0,
        strategy="scalping_breakout",
        stop_pct=0.1,
        take_pct=0.2,
    )
    assert pnl == 0
    pnl = portfolio.update_on_fill(
        "BTCUSDT",
        "SELL",
        0.1,
        110.0,
        strategy="scalping_breakout",
    )
    assert pnl > 0
    position = portfolio.get_position("BTCUSDT")
    assert position.strategy == "scalping_breakout"
    assert portfolio.realized_pnl == pnl
