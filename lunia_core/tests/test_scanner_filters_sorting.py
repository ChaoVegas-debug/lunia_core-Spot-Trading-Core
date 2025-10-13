from app.services.arbitrage.scanner import ArbitrageFilters, ArbitrageOpportunity
from app.services.arbitrage.ui import format_filters


def make_opp(symbol: str, roi: float, usd: float) -> ArbitrageOpportunity:
    return ArbitrageOpportunity(
        proposal_id=f"{symbol}:{roi}",
        symbol=symbol,
        buy_exchange="A",
        sell_exchange="B",
        buy_price=100.0,
        sell_price=101.0,
        gross_spread_pct=roi + 0.5,
        fees_total_pct=0.5,
        slippage_est_pct=0.1,
        net_roi_pct=roi,
        net_profit_usd=usd,
        qty_usd=100.0,
        created_at=0.0,
        transfer_type="internal",
        latency_ms=10.0,
        meta={},
    )


def test_filters_formatting():
    filters = ArbitrageFilters(min_net_roi_pct=1.0, max_net_roi_pct=5.0, min_net_usd=2.0, top_k=3, sort_key="net_profit_usd", sort_dir="asc")
    text = format_filters(filters)
    assert "ROI 1.00-5.00%" in text
    assert "Top 3" in text
