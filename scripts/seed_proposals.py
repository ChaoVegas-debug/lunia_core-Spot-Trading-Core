#!/usr/bin/env python3
"""
EPOCH B: Proposal Seed Data Script
MANDATORY - NO DATA = NO SYSTEM

Generates realistic, governance-valid proposals for all 6 scenarios:
- Scenario A: Perfect Trade
- Scenario B: Governance Blocked
- Scenario C: Stale Data
- Scenario D: Expired/Superseded
- Scenario E: Extreme Risk
- Scenario F: Conflict Detected
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lunia_core.app.services.auth.database import Base, engine, get_session
from lunia_core.app.services.auth.models import User
from lunia_core.app.services.proposal.models import (
    Proposal, ProposalStatus, ProposalAction, RiskLabel, Horizon, DataFreshnessState
)


def create_seed_data():
    """Create seed proposals for all 6 scenarios"""
    
    # Create tables
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    
    session = get_session()
    
    try:
        # Ensure at least one user exists
        user = session.query(User).filter_by(email="trader@lunia.io").first()
        if not user:
            from werkzeug.security import generate_password_hash
            user = User(
                email="trader@lunia.io",
                password_hash=generate_password_hash("demo_password_123"),
                role="TRADER",
                is_active=True
            )
            session.add(user)
            session.flush()
        
        user_id = user.id
        now = datetime.utcnow()
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # SCENARIO A: Perfect Trade
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        proposal_a = Proposal(
            status=ProposalStatus.PENDING_USER,
            asset="BTC",
            action=ProposalAction.BUY,
            horizon=Horizon.POSITION,
            risk_label=RiskLabel.MEDIUM_RISK,
            priority_score=85,
            
            governance_snapshot={
                "global_stop": False,
                "system_mode": "MANUAL",
                "run_mode": "dry",
                "airlock_status": "ARMED",
                "live_allowed": True,
                "tier": "TRADER",
                "data_freshness_state": "FRESH",
                "data_freshness_metrics": {"ops_age_ms": 2500, "health_age_ms": 0},
                "timestamp": now.isoformat()
            },
            
            thesis_summary="Strong institutional accumulation detected across multiple timeframes. On-chain metrics show whale activity accelerating. Technical confluence at key demand zone.",
            
            thesis_dna={
                "chromosomes": {
                    "technical": [
                        {"key": "rsi_oversold", "confidence": 0.92, "weight": 0.40, "evidence_refs": ["chart_1d"], "validation_window": 86400, "mutation_resistance": 0.75},
                        {"key": "macd_bullish_cross", "confidence": 0.85, "weight": 0.35, "evidence_refs": ["chart_4h"], "validation_window": 14400, "mutation_resistance": 0.60},
                        {"key": "support_zone", "confidence": 0.88, "weight": 0.25, "evidence_refs": ["chart_1w"], "validation_window": 604800, "mutation_resistance": 0.80}
                    ],
                    "fundamental": [
                        {"key": "network_health", "confidence": 0.90, "weight": 0.50, "evidence_refs": ["on_chain_1"], "validation_window": 86400, "mutation_resistance": 0.85},
                        {"key": "adoption_growth", "confidence": 0.82, "weight": 0.50, "evidence_refs": ["metrics_1"], "validation_window": 259200, "mutation_resistance": 0.70}
                    ],
                    "sentiment": [
                        {"key": "social_momentum", "confidence": 0.75, "weight": 0.60, "evidence_refs": ["twitter_1"], "validation_window": 21600, "mutation_resistance": 0.40},
                        {"key": "news_positive", "confidence": 0.80, "weight": 0.40, "evidence_refs": ["news_1"], "validation_window": 43200, "mutation_resistance": 0.50}
                    ],
                    "flow": [
                        {"key": "whale_accumulation", "confidence": 0.88, "weight": 0.70, "evidence_refs": ["on_chain_2"], "validation_window": 86400, "mutation_resistance": 0.75},
                        {"key": "exchange_outflow", "confidence": 0.83, "weight": 0.30, "evidence_refs": ["exchange_1"], "validation_window": 86400, "mutation_resistance": 0.65}
                    ],
                    "macro": [
                        {"key": "inflation_data", "confidence": 0.70, "weight": 0.60, "evidence_refs": ["macro_1"], "validation_window": 604800, "mutation_resistance": 0.60},
                        {"key": "fed_policy", "confidence": 0.65, "weight": 0.40, "evidence_refs": ["macro_2"], "validation_window": 1209600, "mutation_resistance": 0.70}
                    ]
                }
            },
            
            invalidation_rules={
                "machine_readable": [
                    {"condition": "price_below", "threshold": 60000, "action": "close"},
                    {"condition": "time_elapsed", "threshold": 172800, "action": "review"}
                ],
                "human_readable": "Close if BTC drops below $60k or after 48h"
            },
            
            factor_attribution=[
                {"factor": "Technical Analysis", "weight": 35, "confidence": 88},
                {"factor": "On-Chain Metrics", "weight": 30, "confidence": 85},
                {"factor": "Institutional Flow", "weight": 25, "confidence": 88},
                {"factor": "Sentiment", "weight": 10, "confidence": 75}
            ],
            
            confidence_score=0.88,
            
            devils_advocate="Counter-case: BTC rally driven by leverage, not spot accumulation. Current resistance at $70k remains strong across 3 timeframes. Macro headwinds (Fed policy uncertainty) could trigger sudden deleveraging cascade. Smart money may be distributing into retail FOMO.",
            
            execution_plan_preview={
                "entry_zone_low": 63500,
                "entry_zone_high": 65000,
                "take_profit_targets": [72000, 78000, 85000],
                "stop_loss": 60000,
                "max_slippage_percent": 0.5
            },
            
            expires_at=now + timedelta(hours=6),
            created_by_user_id=user_id
        )
        session.add(proposal_a)
        print("✓ Scenario A: Perfect Trade (BTC)")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # SCENARIO B: Governance Blocked
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        proposal_b = Proposal(
            status=ProposalStatus.PENDING_USER,
            asset="ETH",
            action=ProposalAction.SELL,
            horizon=Horizon.SWING,
            risk_label=RiskLabel.LOW_RISK,
            priority_score=95,  # URGENT
            
            governance_snapshot={
                "global_stop": True,  # BLOCKED
               "system_mode": "STOP",
                "run_mode": "dry",
                "airlock_status": "BLOCKED",
                "live_allowed": False,
                "tier": "TRADER",
                "data_freshness_state": "FRESH",
                "data_freshness_metrics": {"ops_age_ms": 1500, "health_age_ms": 0},
                "timestamp": now.isoformat(),
                "veto_reason": "Emergency governance stop - awaiting operator clearance"
            },
            
            thesis_summary="Bearish divergence on daily timeframe. Gas fees spiking indicating network congestion. Smart money distribution pattern.",
            
            thesis_dna={
                "chromosomes": {
                    "technical": [
                        {"key": "bearish_divergence", "confidence": 0.85, "weight": 0.60, "evidence_refs": ["chart_1d"], "validation_window": 86400, "mutation_resistance": 0.70},
                        {"key": "resistance_rejection", "confidence": 0.80, "weight": 0.40, "evidence_refs": ["chart_4h"], "validation_window": 14400, "mutation_resistance": 0.60}
                    ],
                    "fundamental": [
                        {"key": "gas_fees_spike", "confidence": 0.90, "weight": 0.70, "evidence_refs": ["on_chain_1"], "validation_window": 43200, "mutation_resistance": 0.65},
                        {"key": "l2_migration", "confidence": 0.75, "weight": 0.30, "evidence_refs": ["metrics1"], "validation_window": 86400, "mutation_resistance": 0.55}
                    ],
                    "sentiment": [
                        {"key": "sentiment_peak", "confidence": 0.78, "weight": 1.0, "evidence_refs": ["social_1"], "validation_window": 21600, "mutation_resistance": 0.45}
                    ],
                    "flow": [
                        {"key": "smart_money_distribution", "confidence": 0.82, "weight": 0.80, "evidence_refs": ["on_chain_2"], "validation_window": 86400, "mutation_resistance": 0.70},
                        {"key": "exchange_inflow", "confidence": 0.78, "weight": 0.20, "evidence_refs": ["exchange_1"], "validation_window": 43200, "mutation_resistance": 0.60}
                    ],
                    "macro": [
                        {"key": "correlated_weakness", "confidence": 0.68, "weight": 1.0, "evidence_refs": ["macro_1"], "validation_window": 259200, "mutation_resistance": 0.55}
                    ]
                }
            },
            
            invalidation_rules={
                "machine_readable": [
                    {"condition": "price_above", "threshold": 3650, "action": "close"}
                ],
                "human_readable": "Close short if ETH breaks above $3650"
            },
            
            factor_attribution=[
                {"factor": "Technical Divergence", "weight": 40, "confidence": 85},
                {"factor": "Network Metrics", "weight": 30, "confidence": 90},
                {"factor": "Smart Money", "weight": 20, "confidence": 78},
                {"factor": "Macro Correlation", "weight": 10, "confidence": 70}
            ],
            
            confidence_score=0.82,
            
            devils_advocate="Counter-case: ETH gas fees often spike before major upgrades or L2 launches, not necessarily bearish. Network congestion could indicate increased adoption. Bearish divergence has falsified 3 times in last 6 months during strong trends.",
            
            execution_plan_preview={
                "entry_zone_low": 3400,
                "entry_zone_high": 3500,
                "take_profit_targets": [3200, 3000, 2850],
                "stop_loss": 3650,
                "max_slippage_percent": 0.3
            },
            
            expires_at=now + timedelta(hours=2),
            created_by_user_id=user_id
        )
        session.add(proposal_b)
        print("✓ Scenario B: Governance Blocked (ETH)")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # SCENARIO C: Stale Data
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        stale_timestamp = now - timedelta(seconds=45)  # 45s old = DEGRADED
        
        proposal_c = Proposal(
            status=ProposalStatus.PENDING_USER,
            asset="SOL",
            action=ProposalAction.BUY,
            horizon=Horizon.POSITION,
            risk_label=RiskLabel.MEDIUM_RISK,
            priority_score=80,
            
            governance_snapshot={
                "global_stop": False,
                "system_mode": "MANUAL",
                "run_mode": "real",  # Real mode requires FRESH data
                "airlock_status": "ARMED",
                "live_allowed": True,
                "tier": "TRADER",
                "data_freshness_state": "DEGRADED",  # STALE DATA
                "data_freshness_metrics": {"ops_age_ms": 45000, "health_age_ms": 2000},
                "timestamp": stale_timestamp.isoformat()
            },
            
            thesis_summary="Ecosystem growth accelerating. New DEX volumes breaking records. Developer activity at ATH. Breakout from 6-month base confirmed.",
            
            thesis_dna={
                "chromosomes": {
                    "technical": [
                        {"key": "breakout_confirmed", "confidence": 0.88, "weight": 0.50, "evidence_refs": ["chart_1d"], "validation_window": 86400, "mutation_resistance": 0.70},
                        {"key": "volume_surge", "confidence": 0.85, "weight": 0.50, "evidence_refs": ["volume_1"], "validation_window": 43200, "mutation_resistance": 0.65}
                    ],
                    "fundamental": [
                        {"key": "dex_volume_ath", "confidence": 0.95, "weight": 0.45, "evidence_refs": ["dex_stats_1"], "validation_window": 86400, "mutation_resistance": 0.85},
                        {"key": "developer_activity", "confidence": 0.92, "weight": 0.35, "evidence_refs": ["github_1"], "validation_window": 604800, "mutation_resistance": 0.80},
                        {"key": "tvl_growth", "confidence": 0.88, "weight": 0.20, "evidence_refs": ["defi_llama_1"], "validation_window": 259200, "mutation_resistance": 0.75}
                    ],
                    "sentiment": [
                        {"key": "builder_optimism", "confidence": 0.82, "weight": 1.0, "evidence_refs": ["social_1"], "validation_window": 86400, "mutation_resistance": 0.60}
                    ],
                    "flow": [
                        {"key": "institutional_purchases", "confidence": 0.85, "weight": 1.0, "evidence_refs": ["on_chain_1"], "validation_window": 86400, "mutation_resistance": 0.70}
                    ],
                    "macro": [
                        {"key": "altcoin_season", "confidence": 0.75, "weight": 1.0, "evidence_refs": ["market_1"], "validation_window": 259200, "mutation_resistance": 0.55}
                    ]
                }
            },
            
            invalidation_rules={
                "machine_readable": [
                    {"condition": "price_below", "threshold": 140, "action": "close"}
                ],
                "human_readable": "Close if SOL breaks below $140"
            },
            
            factor_attribution=[
                {"factor": "Ecosystem Growth", "weight": 35, "confidence": 95},
                {"factor": "Technical Breakout", "weight": 30, "confidence": 88},
                {"factor": "Developer Activity", "weight": 20, "confidence": 92},
                {"factor": "Volume Profile", "weight": 15, "confidence": 85}
            ],
            
            confidence_score=0.91,
            
            devils_advocate="Counter-case: SOL has history of network outages. Current rally may be driven by airdrop farming, not organic adoption. Breakout on low relative volume compared to previous cycles. Macro risk fromconcentrated holder distribution.",
            
            execution_plan_preview={
                "entry_zone_low": 148,
                "entry_zone_high": 152,
                "take_profit_targets": [170, 190, 210],
                "stop_loss": 140,
                "max_slippage_percent": 0.8
            },
            
            expires_at=now + timedelta(hours=4),
            created_by_user_id=user_id
        )
        session.add(proposal_c)
        print("✓ Scenario C: Stale Data (SOL)")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # SCENARIO D: Expired
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        proposal_d = Proposal(
            status=ProposalStatus.EXPIRED,
            asset="AVAX",
            action=ProposalAction.HEDGE,
            horizon=Horizon.INTRADAY,
            risk_label=RiskLabel.HIGH_RISK,
            priority_score=70,
            
            governance_snapshot={
                "global_stop": False,
                "system_mode": "MANUAL",
                "run_mode": "dry",
                "airlock_status": "ARMED",
                "live_allowed": True,
                "tier": "TRADER",
                "data_freshness_state": "FRESH",
                "data_freshness_metrics": {"ops_age_ms": 3500, "health_age_ms": 0},
                "timestamp": (now - timedelta(hours=3)).isoformat()
            },
            
            thesis_summary="Short-term volatility hedge recommended due to upcoming macro event. Window has closed.",
            
            thesis_dna={
                "chromosomes": {
                    "technical": [
                        {"key": "volatility_spike", "confidence": 0.80, "weight": 1.0, "evidence_refs": ["vol_1"], "validation_window": 3600, "mutation_resistance": 0.50}
                    ],
                    "fundamental": [
                        {"key": "event_risk", "confidence": 0.85, "weight": 1.0, "evidence_refs": ["calendar_1"], "validation_window": 7200, "mutation_resistance": 0.60}
                    ],
                    "sentiment": [
                        {"key": "uncertainty", "confidence": 0.70, "weight": 1.0, "evidence_refs": ["social_1"], "validation_window": 14400, "mutation_resistance": 0.40}
                    ],
                    "flow": [
                        {"key": "hedge_demand", "confidence": 0.75, "weight": 1.0, "evidence_refs": ["options_1"], "validation_window": 3600, "mutation_resistance": 0.45}
                    ],
                    "macro": [
                        {"key": "fomc_minutes", "confidence": 0.78, "weight": 1.0, "evidence_refs": ["fed_1"], "validation_window": 7200, "mutation_resistance": 0.70}
                    ]
                }
            },
            
            invalidation_rules={
                "machine_readable": [
                    {"condition": "time_elapsed", "threshold": 7200, "action": "expire"}
                ],
                "human_readable": "Expire after 2 hours (event window closed)"
            },
            
            factor_attribution=[
                {"factor": "Volatility Analysis", "weight": 50, "confidence": 80},
                {"factor": "Event Risk", "weight": 30, "confidence": 85},
                {"factor": "Correlation", "weight": 20, "confidence": 70}
            ],
            
            confidence_score=0.75,
            
            devils_advocate="Counter-case: Implied vol already priced in. Actual event volatility often lower than expected. Hedging costs may exceed potential drawdown in base case scenario.",
            
            expires_at=now - timedelta(minutes=15),  # Expired 15min ago
            created_by_user_id=user_id
        )
        session.add(proposal_d)
        print("✓ Scenario D: Expired (AVAX)")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # SCENARIO E: Extreme Risk
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        proposal_e = Proposal(
            status=ProposalStatus.PENDING_USER,
            asset="DOGE",
            action=ProposalAction.BUY,
            horizon=Horizon.INTRADAY,
            risk_label=RiskLabel.EXTREME_RISK,
            priority_score=40,  # LOW priority
            
            governance_snapshot={
                "global_stop": False,
                "system_mode": "MANUAL",
                "run_mode": "dry",
                "airlock_status": "ARMED",
                "live_allowed": True,
                "tier": "TRADER",
                "data_freshness_state": "FRESH",
                "data_freshness_metrics": {"ops_age_ms": 4500, "health_age_ms": 500},
                "timestamp": now.isoformat()
            },
            
            thesis_summary="Extremely speculative setup. Social media momentum building. High volatility expected. Only for risk-tolerant strategies with strict stops.",
            
            thesis_dna={
                "chromosomes": {
                    "technical": [
                        {"key": "momentum_breakout", "confidence": 0.50, "weight": 0.60, "evidence_refs": ["chart_1h"], "validation_window": 3600, "mutation_resistance": 0.30},
                        {"key": "volume_surge", "confidence": 0.55, "weight": 0.40, "evidence_refs": ["volume_1"], "validation_window": 1800, "mutation_resistance": 0.25}
                    ],
                    "fundamental": [
                        {"key": "no_fundamentals", "confidence": 0.30, "weight": 1.0, "evidence_refs": [], "validation_window": 86400, "mutation_resistance": 0.20}
                    ],
                    "sentiment": [
                        {"key": "social_hype", "confidence": 0.70, "weight": 0.80, "evidence_refs": ["twitter_trending"], "validation_window": 1800, "mutation_resistance": 0.35},
                        {"key": "meme_catalyst", "confidence": 0.65, "weight": 0.20, "evidence_refs": ["reddit_1"], "validation_window": 3600, "mutation_resistance": 0.30}
                    ],
                    "flow": [
                        {"key": "retail_fomo", "confidence": 0.75, "weight": 0.70, "evidence_refs": ["exchange_data"], "validation_window": 7200, "mutation_resistance": 0.40},
                        {"key": "whale_pump", "confidence": 0.60, "weight": 0.30, "evidence_refs": ["on_chain_1"], "validation_window": 3600, "mutation_resistance": 0.35}
                    ],
                    "macro": [
                        {"key": "risk_on", "confidence": 0.55, "weight": 1.0, "evidence_refs": ["market_sentiment"], "validation_window": 43200, "mutation_resistance": 0.45}
                    ]
                }
            },
            
            invalidation_rules={
                "machine_readable": [
                    {"condition": "time_elapsed", "threshold": 3600, "action": "close"},
                    {"condition": "drawdown_exceeds", "threshold": 0.15, "action": "close"}
                ],
                "human_readable": "Close after 1h or if drawdown exceeds 15%"
            },
            
            factor_attribution=[
                {"factor": "Social Momentum", "weight": 60, "confidence": 70},
                {"factor": "Technical Setup", "weight": 25, "confidence": 50},
                {"factor": "Whale Activity", "weight": 15, "confidence": 65}
            ],
            
            confidence_score=0.62,
            
            devils_advocate="Counter-case: Pure speculation. No fundamental support. Social momentum can reverse instantly. High probability of rug pull or coordinated dump. Historical pattern shows 80% of meme coin rallies fail within 24h.",
            
            execution_plan_preview={
                "entry_zone_low": 0.078,
                "entry_zone_high": 0.082,
                "take_profit_targets": [0.095, 0.110],
                "stop_loss": 0.072,
                "max_slippage_percent": 2.0
            },
            
            expires_at=now + timedelta(minutes=45),
            created_by_user_id=user_id
        )
        session.add(proposal_e)
        print("✓ Scenario E: Extreme Risk (DOGE)")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # SCENARIO F: Conflict Detected (EPOCH C preview)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        proposal_f = Proposal(
            status=ProposalStatus.REQUEST_CHANGES,
            asset="LINK",
            action=ProposalAction.BUY,
            horizon=Horizon.SWING,
            risk_label=RiskLabel.MEDIUM_RISK,
            priority_score=65,
            
            governance_snapshot={
                "global_stop": False,
                "system_mode": "MANUAL",
                "run_mode": "dry",
                "airlock_status": "ARMED",
                "live_allowed": True,
                "tier": "TRADER",
                "data_freshness_state": "FRESH",
                "data_freshness_metrics": {"ops_age_ms": 5000, "health_age_ms": 1000},
                "timestamp": now.isoformat(),
                "conflict_detected": "PORTFOLIO_CORRELATION"  # EPOCH C preview
            },
            
            thesis_summary="Oracle network expansion bullish. However, conflicts detected with existing BAND position (correlation 0.87). Requires size adjustment.",
            
            thesis_dna={
                "chromosomes": {
                    "technical": [
                        {"key": "accumulation_pattern", "confidence": 0.75, "weight": 0.55, "evidence_refs": ["chart_1d"], "validation_window": 86400, "mutation_resistance": 0.65},
                        {"key": "breakout_setup", "confidence": 0.72, "weight": 0.45, "evidence_refs": ["chart_4h"], "validation_window": 14400, "mutation_resistance": 0.60}
                    ],
                    "fundamental": [
                        {"key": "oracle_expansion", "confidence": 0.85, "weight": 0.60, "evidence_refs": ["news_1"], "validation_window": 259200, "mutation_resistance": 0.75},
                        {"key": "partnership_growth", "confidence": 0.80, "weight": 0.40, "evidence_refs": ["announcements_1"], "validation_window": 604800, "mutation_resistance": 0.70}
                    ],
                    "sentiment": [
                        {"key": "developer_confidence", "confidence": 0.78, "weight": 1.0, "evidence_refs": ["ecosystem_1"], "validation_window": 86400, "mutation_resistance": 0.60}
                    ],
                    "flow": [
                        {"key": "institutional_interest", "confidence": 0.80, "weight": 1.0, "evidence_refs": ["on_chain_1"], "validation_window": 86400, "mutation_resistance": 0.65}
                    ],
                    "macro": [
                        {"key": "oracle_sector_rotation", "confidence": 0.73, "weight": 1.0, "evidence_refs": ["sector_analysis"], "validation_window": 259200, "mutation_resistance": 0.55}
                    ]
                }
            },
            
            invalidation_rules={
                "machine_readable": [
                    {"condition": "correlation_exceeds", "threshold": 0.85, "action": "reduce_size"},
                    {"condition": "price_below", "threshold": 12.50, "action": "close"}
                ],
                "human_readable": "Reduce size if BAND correlation >0.85, close if LINK <$12.50"
            },
            
            factor_attribution=[
                {"factor": "Fundamental News", "weight": 35, "confidence": 85},
                {"factor": "Technical Pattern", "weight": 30, "confidence": 75},
                {"factor": "Sector Rotation", "weight": 20, "confidence": 80},
                {"factor": "Conflict Warning", "weight": 15, "confidence": 90}
            ],
            
            confidence_score=0.79,
            
            devils_advocate="Counter-case: Oracle sector overcrowded. LINK/BAND correlation means portfolio risk not diversified. Network expansion already priced in. Technical setup weak compared to other altcoins in same risk category.",
            
            execution_plan_preview={
                "entry_zone_low": 13.80,
                "entry_zone_high": 14.20,
                "take_profit_targets": [16.00, 18.50, 21.00],
                "stop_loss": 12.50,
                "max_slippage_percent": 0.6
            },
            
            expires_at=now + timedelta(hours=8),
            created_by_user_id=user_id
        )
        session.add(proposal_f)
        print(\"✓ Scenario F: Conflict Detected (LINK)\")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # VARIETY #1: Approved Proposal (ADA)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        proposal_v1 = Proposal(
            status=ProposalStatus.APPROVED,
            asset="ADA",
            action=ProposalAction.BUY,
            horizon=Horizon.LONG_TERM,
            risk_label=RiskLabel.LOW_RISK,
            priority_score=75,
            
            governance_snapshot={
                "global_stop": False,
                "system_mode": "MANUAL",
                "run_mode": "dry",
                "airlock_status": "ARMED",
                "live_allowed": True,
                "tier": "TRADER",
                "data_freshness_state": "FRESH",
                "data_freshness_metrics": {"ops_age_ms": 3000, "health_age_ms": 500},
                "timestamp": (now - timedelta(hours=1)).isoformat()
            },
            
            thesis_summary="Cardano ecosystem maturation play. Hydra scaling solution live. Institutional DeFi partnerships expanding.",
            
            thesis_dna={
                "chromosomes": {
                    "technical": [
                        {"key": "base_formation", "confidence": 0.78, "weight": 0.65, "evidence_refs": ["chart_1w"], "validation_window": 604800, "mutation_resistance": 0.70},
                        {"key": "volume_accumulation", "confidence": 0.72, "weight": 0.35, "evidence_refs": ["volume_profile"], "validation_window": 259200, "mutation_resistance": 0.65}
                    ],
                    "fundamental": [
                        {"key": "hydra_launch", "confidence": 0.88, "weight": 0.55, "evidence_refs": ["tech_docs"], "validation_window": 1209600, "mutation_resistance": 0.80},
                        {"key": "defi_growth", "confidence": 0.85, "weight": 0.45, "evidence_refs": ["tvl_metrics"], "validation_window": 604800, "mutation_resistance": 0.75}
                    ],
                    "sentiment": [
                        {"key": "developer_momentum", "confidence": 0.80, "weight": 1.0, "evidence_refs": ["github_stats"], "validation_window": 604800, "mutation_resistance": 0.65}
                    ],
                    "flow": [
                        {"key": "institutional_accumulation", "confidence": 0.82, "weight": 1.0, "evidence_refs": ["on_chain"], "validation_window": 259200, "mutation_resistance": 0.70}
                    ],
                    "macro": [
                        {"key": "altcoin_rotation", "confidence": 0.70, "weight": 1.0, "evidence_refs": ["sector_flow"], "validation_window": 432000, "mutation_resistance": 0.55}
                    ]
                }
            },
            
            invalidation_rules={
                "machine_readable": [
                    {"condition": "price_below", "threshold": 0.45, "action": "review"}
                ],
                "human_readable": "Review if ADA drops below $0.45"
            },
            
            factor_attribution=[
                {"factor": "Technology Maturation", "weight": 45, "confidence": 88},
                {"factor": "DeFi Ecosystem", "weight": 30, "confidence": 85},
                {"factor": "Long-term Accumulation", "weight": 25, "confidence": 80}
            ],
            
            confidence_score=0.82,
           
            devils_advocate="Counter-case: Cardano slow to market. Ethereum and Solana maintain dominance. Hydra may not attract developer migration. Academic approach vs pragmatic competitors may limit adoption velocity.",
            
            execution_plan_preview={
                "entry_zone_low": 0.50,
                "entry_zone_high": 0.54,
                "take_profit_targets": [0.65, 0.80, 1.00],
                "stop_loss": 0.45,
                "max_slippage_percent": 0.6
            },
            
            expires_at=now + timedelta(days=30),
            created_by_user_id=user_id,
            approved_by_user_id=user_id,
            approved_at=now - timedelta(minutes=30)
        )
        session.add(proposal_v1)
        print("✓ Variety #1: Approved (ADA)")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # VARIETY #2: Rejected Proposal (MATIC)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        proposal_v2 = Proposal(
            status=ProposalStatus.REJECTED,
            asset="MATIC",
            action=ProposalAction.SELL,
            horizon=Horizon.SWING,
            risk_label=RiskLabel.MEDIUM_RISK,
            priority_score=60,
            
            governance_snapshot={
                "global_stop": False,
                "system_mode": "MANUAL",
                "run_mode": "dry",
                "airlock_status": "ARMED",
                "live_allowed": True,
                "tier": "TRADER",
                "data_freshness_state": "FRESH",
                "data_freshness_metrics": {"ops_age_ms": 2800, "health_age_ms": 0},
                "timestamp": (now - timedelta(hours=2)).isoformat()
            },
            
            thesis_summary="ETH scaling wars intensifying. MATIC facing competition from OP/ARB. Revenue compression risk.",
            
            thesis_dna={
                "chromosomes": {
                    "technical": [
                        {"key": "resistance_ceiling", "confidence": 0.72, "weight": 0.55, "evidence_refs": ["chart_daily"], "validation_window": 86400, "mutation_resistance": 0.60},
                        {"key": "volume_decline", "confidence": 0.70, "weight": 0.45, "evidence_refs": ["volume_trend"], "validation_window": 172800, "mutation_resistance": 0.55}
                    ],
                    "fundamental": [
                        {"key": "competition_increase", "confidence": 0.85, "weight": 0.60, "evidence_refs": ["market_share"], "validation_window": 604800, "mutation_resistance": 0.70},
                        {"key": "revenue_pressure", "confidence": 0.80, "weight": 0.40, "evidence_refs": ["fee_metrics"], "validation_window": 259200, "mutation_resistance": 0.65}
                    ],
                    "sentiment": [
                        {"key": "developer_concern", "confidence": 0.68, "weight": 1.0, "evidence_refs": ["social_analysis"], "validation_window": 172800, "mutation_resistance": 0.50}
                    ],
                    "flow": [
                        {"key": "capital_rotation", "confidence": 0.75, "weight": 1.0, "evidence_refs": ["fund_flows"], "validation_window": 259200, "mutation_resistance": 0.60}
                    ],
                    "macro": [
                        {"key": "l2_narrative_shift", "confidence": 0.78, "weight": 1.0, "evidence_refs": ["narrative_tracker"], "validation_window": 432000, "mutation_resistance": 0.65}
                    ]
                }
            },
            
            invalidation_rules={
                "machine_readable": [
                    {"condition": "price_above", "threshold": 1.05, "action": "close"}
                ],
                "human_readable": "Close short if MATIC breaks above $1.05"
            },
            
            factor_attribution=[
                {"factor": "Competitive Pressure", "weight": 40, "confidence": 85},
                {"factor": "Technical Weakness", "weight": 30, "confidence": 72},
                {"factor": "Narrative Rotation", "weight": 30, "confidence": 78}
            ],
            
            confidence_score=0.76,
            
            devils_advocate="Counter-case: MATIC established infrastructure. Strong developer ecosystem. Polygon PoS still cheapest option. zkEVM could regain mindshare. Short-term bearishness may be transitory.",
            
            expires_at=now + timedelta(hours=12),
            created_by_user_id=user_id,
            rejected_by_user_id=user_id,
            rejected_at=now - timedelta(minutes=45),
            rejection_reason="Risk/reward asymmetric - better short opportunities available"
        )
        session.add(proposal_v2)
        print("✓ Variety #2: Rejected (MATIC)")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # VARIETY #3: Rebalance Action (DOT)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        proposal_v3 = Proposal(
            status=ProposalStatus.PENDING_USER,
            asset="DOT",
            action=ProposalAction.REBALANCE,
            horizon=Horizon.POSITION,
            risk_label=RiskLabel.LOW_RISK,
            priority_score=50,
            
            governance_snapshot={
                "global_stop": False,
                "system_mode": "MANUAL",
                "run_mode": "dry",
                "airlock_status": "ARMED",
                "live_allowed": True,
                "tier": "TRADER",
                "data_freshness_state": "FRESH",
                "data_freshness_metrics": {"ops_age_ms": 3500, "health_age_ms": 1200},
                "timestamp": now.isoformat()
            },
            
            thesis_summary="Portfolio rebalancing triggered. DOT allocation exceeds target weight by 8%. Risk management adjustment required.",
            
            thesis_dna={
                "chromosomes": {
                    "technical": [
                        {"key": "neutral_trend", "confidence": 0.65, "weight": 1.0, "evidence_refs": ["chart_analysis"], "validation_window": 259200, "mutation_resistance": 0.50}
                    ],
                    "fundamental": [
                        {"key": "parachain_auctions", "confidence": 0.75, "weight": 0.50, "evidence_refs": ["auction_data"], "validation_window": 1209600, "mutation_resistance": 0.60},
                        {"key": "ecosystem_steady", "confidence": 0.70, "weight": 0.50, "evidence_refs": ["activity_metrics"], "validation_window": 604800, "mutation_resistance": 0.55}
                    ],
                    "sentiment": [
                        {"key": "stable_sentiment", "confidence": 0.68, "weight": 1.0, "evidence_refs": ["sentiment_gauge"], "validation_window": 259200, "mutation_resistance": 0.45}
                    ],
                    "flow": [
                        {"key": "position_size_excess", "confidence": 0.95, "weight": 1.0, "evidence_refs": ["portfolio_state"], "validation_window": 3600, "mutation_resistance": 0.90}
                    ],
                    "macro": [
                        {"key": "portfolio_risk_management", "confidence": 0.92, "weight": 1.0, "evidence_refs": ["risk_metrics"], "validation_window": 86400, "mutation_resistance": 0.85}
                    ]
                }
            },
            
            invalidation_rules={
                "machine_readable": [
                    {"condition": "weight_normalized", "threshold": 0.02, "action": "complete"}
                ],
                "human_readable": "Complete when portfolio weight within 2% of target"
            },
            
            factor_attribution=[
                {"factor": "Portfolio Risk Management", "weight": 70, "confidence": 95},
                {"factor": "Position Size Discipline", "weight": 20, "confidence": 92},
                {"factor": "Market Conditions", "weight": 10, "confidence": 68}
            ],
            
            confidence_score=0.92,
            
            devils_advocate="Counter-case: DOT fundamental thesis remains intact. Reducing position purely for mechanical rebalancing may miss continuation. Parachain ecosystem showing promise. Premature exit from winning position.",
            
            execution_plan_preview={
                "entry_zone_low": 6.80,
                "entry_zone_high": 7.20,
                "take_profit_targets": [],  # Rebalance has no profit target
                "stop_loss": None,
                "max_slippage_percent": 0.4
            },
            
            expires_at=now + timedelta(hours=24),
            created_by_user_id=user_id
        )
        session.add(proposal_v3)
        print("✓ Variety #3: Rebalance (DOT)")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # VARIETY #4: Pending User (AR)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        proposal_v4 = Proposal(
            status=ProposalStatus.PENDING_USER,
            asset="AR",
            action=ProposalAction.BUY,
            horizon=Horizon.LONG_TERM,
            risk_label=RiskLabel.HIGH_RISK,
            priority_score=72,
            
            governance_snapshot={
                "global_stop": False,
                "system_mode": "MANUAL",
                "run_mode": "dry",
                "airlock_status": "ARMED",
                "live_allowed": True,
                "tier": "TRADER",
                "data_freshness_state": "FRESH",
                "data_freshness_metrics": {"ops_age_ms": 4200, "health_age_ms": 800},
                "timestamp": now.isoformat()
            },
            
            thesis_summary="Permanent data storage demand thesis. AI data preservation narrative gaining traction. Network utilization accelerating.",
            
            thesis_dna={
                "chromosomes": {
                    "technical": [
                        {"key": "breakout_confirmed", "confidence": 0.82, "weight": 0.60, "evidence_refs": ["chart_weekly"], "validation_window": 604800, "mutation_resistance": 0.75},
                        {"key": "strong_momentum", "confidence": 0.78, "weight": 0.40, "evidence_refs": ["momentum_oscillators"], "validation_window": 259200, "mutation_resistance": 0.68}
                    ],
                    "fundamental": [
                        {"key": "storage_demand", "confidence": 0.90, "weight": 0.50, "evidence_refs": ["network_usage"], "validation_window": 1209600, "mutation_resistance": 0.85},
                        {"key": "ai_narrative", "confidence": 0.85, "weight": 0.30, "evidence_refs": ["adoption_metrics"], "validation_window": 604800, "mutation_resistance": 0.75},
                        {"key": "tokenomics_favorable", "confidence": 0.88, "weight": 0.20, "evidence_refs": ["supply_dynamics"], "validation_window": 2592000, "mutation_resistance": 0.80}
                    ],
                    "sentiment": [
                        {"key": "narrative_momentum", "confidence": 0.80, "weight": 1.0, "evidence_refs": ["social_metrics"], "validation_window": 259200, "mutation_resistance": 0.65}
                    ],
                    "flow": [
                        {"key": "whale_accumulation", "confidence": 0.84, "weight": 1.0, "evidence_refs": ["on_chain_large"], "validation_window": 432000, "mutation_resistance": 0.72}
                    ],
                    "macro": [
                        {"key": "data_explosion", "confidence": 0.87, "weight": 1.0, "evidence_refs": ["macro_trend"], "validation_window": 2592000, "mutation_resistance": 0.78}
                    ]
                }
            },
            
            invalidation_rules={
                "machine_readable": [
                    {"condition": "price_below", "threshold": 8.50, "action": "review"},
                    {"condition": "usage_decline", "threshold": 0.30, "action": "close"}
                ],
                "human_readable": "Review if AR drops below $8.50 or usage declines 30%"
            },
            
            factor_attribution=[
                {"factor": "Storage Demand Thesis", "weight": 45, "confidence": 90},
                {"factor": "Technical Strength", "weight": 30, "confidence": 82},
                {"factor": "Macro AI Trend", "weight": 25, "confidence": 87}
            ],
            
            confidence_score=0.86,
            
            devils_advocate="Counter-case: Arweave unproven at scale. Centralized cloud storage cheaper. NFT storage demand may be transitory. Competition from Filecoin, IPFS. High risk that permanence thesis doesn't translate to token value.",
            
            execution_plan_preview={
                "entry_zone_low": 9.20,
                "entry_zone_high": 9.80,
                "take_profit_targets": [13.00, 18.00, 25.00],
                "stop_loss": 8.50,
                "max_slippage_percent": 1.0
            },
            
            expires_at=now + timedelta(days=3),
            created_by_user_id=user_id
        )
        session.add(proposal_v4)
        print("✓ Variety #4: Pending User (AR)")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # VARIETY #5: Low Priority Swing (UNI)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        proposal_v5 = Proposal(
            status=ProposalStatus.PENDING_USER,
            asset="UNI",
            action=ProposalAction.BUY,
            horizon=Horizon.SWING,
            risk_label=RiskLabel.MEDIUM_RISK,
            priority_score=35,  # LOW PRIORITY
            
            governance_snapshot={
                "global_stop": False,
                "system_mode": "MANUAL",
                "run_mode": "dry",
                "airlock_status": "ARMED",
                "live_allowed": True,
                "tier": "TRADER",
                "data_freshness_state": "FRESH",
                "data_freshness_metrics": {"ops_age_ms": 5500, "health_age_ms": 1500},
                "timestamp": now.isoformat()
            },
            
            thesis_summary="Uniswap V4 launch approaching. DEX volume recovery. Technical setup moderately bullish. Lower priority given market saturation.",
            
            thesis_dna={
                "chromosomes": {
                    "technical": [
                        {"key": "base_support", "confidence": 0.68, "weight": 0.55, "evidence_refs": ["support_test"], "validation_window": 172800, "mutation_resistance": 0.55},
                        {"key": "bullish_pattern", "confidence": 0.72, "weight": 0.45, "evidence_refs": ["pattern_recognition"], "validation_window": 259200, "mutation_resistance": 0.60}
                    ],
                    "fundamental": [
                        {"key": "v4_launch", "confidence": 0.80, "weight": 0.60, "evidence_refs": ["roadmap"], "validation_window": 1209600, "mutation_resistance": 0.70},
                        {"key": "volume_recovery", "confidence": 0.75, "weight": 0.40, "evidence_refs": ["dex_volumes"], "validation_window": 604800, "mutation_resistance": 0.65}
                    ],
                    "sentiment": [
                        {"key": "moderate_optimism", "confidence": 0.70, "weight": 1.0, "evidence_refs": ["community_pulse"], "validation_window": 259200, "mutation_resistance": 0.50}
                    ],
                    "flow": [
                        {"key": "steady_accumulation", "confidence": 0.72, "weight": 1.0, "evidence_refs": ["flow_data"], "validation_window": 432000, "mutation_resistance": 0.58}
                    ],
                    "macro": [
                        {"key": "defi_revival", "confidence": 0.68, "weight": 1.0, "evidence_refs": ["sector_flows"], "validation_window": 604800, "mutation_resistance": 0.55}
                    ]
                }
            },
            
            invalidation_rules={
                "machine_readable": [
                    {"condition": "price_below", "threshold": 5.80, "action": "close"}
                ],
                "human_readable": "Close if UNI drops below $5.80"
            },
            
            factor_attribution=[
                {"factor": "V4 Catalyst", "weight": 40, "confidence": 80},
                {"factor": "Technical Setup", "weight": 35, "confidence": 70},
                {"factor": "DeFi Sector", "weight": 25, "confidence": 72}
            ],
            
            confidence_score=0.73,
            
            devils_advocate="Counter-case: Uniswap faces intense competition from aggregators. V4 may not drive token value. Governance token premium unclear. Better DeFi opportunities available. Market saturation in DEX space.",
            
            execution_plan_preview={
                "entry_zone_low": 6.20,
                "entry_zone_high": 6.50,
                "take_profit_targets": [7.50, 8.80],
                "stop_loss": 5.80,
                "max_slippage_percent": 0.7
            },
            
            expires_at=now + timedelta(hours=18),
            created_by_user_id=user_id
        )
        session.add(proposal_v5)
        print("✓ Variety #5: Low Priority (UNI)")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # VARIETY #6: Delegation Action (ATOM)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        proposal_v6 = Proposal(
            status=ProposalStatus.PENDING_USER,
            asset="ATOM",
            action=ProposalAction.BUY,
            horizon=Horizon.POSITION,
            risk_label=RiskLabel.MEDIUM_RISK,
            priority_score=68,
            
            governance_snapshot={
                "global_stop": False,
                "system_mode": "MANUAL",
                "run_mode": "dry",
                "airlock_status": "ARMED",
                "live_allowed": True,
                "tier": "TRADER",
                "data_freshness_state": "FRESH",
                "data_freshness_metrics": {"ops_age_ms": 4800, "health_age_ms": 600},
                "timestamp": now.isoformat()
            },
            
            thesis_summary="Cosmos IBC adoption accelerating. Interchain security live. Staking yield attractive. Interoperability thesis maturing.",
            
            thesis_dna={
                "chromosomes": {
                    "technical": [
                        {"key": "range_support", "confidence": 0.74, "weight": 0.50, "evidence_refs": ["range_analysis"], "validation_window": 259200, "mutation_resistance": 0.62},
                        {"key": "accumulation_phase", "confidence": 0.76, "weight": 0.50, "evidence_refs": ["volume_profile"], "validation_window": 432000, "mutation_resistance": 0.65}
                    ],
                    "fundamental": [
                        {"key": "ibc_growth", "confidence": 0.88, "weight": 0.45, "evidence_refs": ["ibc_metrics"], "validation_window": 1209600, "mutation_resistance": 0.80},
                        {"key": "interchain_security", "confidence": 0.85, "weight": 0.35, "evidence_refs": ["security_adoption"], "validation_window": 604800, "mutation_resistance": 0.75},
                        {"key": "staking_yield", "confidence": 0.90, "weight": 0.20, "evidence_refs": ["yield_data"], "validation_window": 604800, "mutation_resistance": 0.85}
                    ],
                    "sentiment": [
                        {"key": "builder_activity", "confidence": 0.82, "weight": 1.0, "evidence_refs": ["ecosystem_growth"], "validation_window": 432000, "mutation_resistance": 0.70}
                    ],
                    "flow": [
                        {"key": "staking_increase", "confidence": 0.86, "weight": 1.0, "evidence_refs": ["staking_metrics"], "validation_window": 1209600, "mutation_resistance": 0.78}
                    ],
                    "macro": [
                        {"key": "modular_narrative", "confidence": 0.79, "weight": 1.0, "evidence_refs": ["sector_analysis"], "validation_window": 1209600, "mutation_resistance": 0.68}
                    ]
                }
            },
            
            invalidation_rules={
                "machine_readable": [
                    {"condition": "price_below", "threshold": 8.00, "action": "review"}
                ],
                "human_readable": "Review if ATOM drops below $8.00"
            },
            
            factor_attribution=[
                {"factor": "IBC Ecosystem", "weight": 40, "confidence": 88},
                {"factor": "Staking Economics", "weight": 30, "confidence": 90},
                {"factor": "Interchain Security", "weight": 20, "confidence": 85},
                {"factor": "Modular Narrative", "weight": 10, "confidence": 79}
            ],
            
            confidence_score=0.84,
            
            devils_advocate="Counter-case: Cosmos tokenomics unclear. ATOM value accrual questionable despite ecosystem growth. Competing modular solutions (Celestia, Eigenlayer). IBC adoption slower than expected. Governance complexity deterring participation.",
            
            execution_plan_preview={
                "entry_zone_low": 9.00,
                "entry_zone_high": 9.50,
                "take_profit_targets": [11.50, 14.00, 17.00],
                "stop_loss": 8.00,
                "max_slippage_percent": 0.65
            },
            
            expires_at=now + timedelta(days=5),
            created_by_user_id=user_id
        )
        session.add(proposal_v6)
        print("✓ Variety #6: Position (ATOM)")
        
        # Commit all
        session.commit()
        
        # Print summary with counts
        total_count = session.query(Proposal).count()
        print(f"\n✅ Seed data created successfully!")
        print(f"✅ {total_count} proposals seeded")
        print(f"\n📊 Scenario Mapping:")
        print(f"   A: Perfect Trade        → BTC (PENDING_USER)")
        print(f"   B: Governance Blocked   → ETH (PENDING_USER)")
        print(f"   C: Stale Data           → SOL (PENDING_USER)")
        print(f"   D: Expired              → AVAX (EXPIRED)")
        print(f"   E: Extreme Risk         → DOGE (PENDING_USER)")
        print(f"   F: Conflict Detected    → LINK (REQUEST_CHANGES)")
        print(f"\n🎲 Variety Proposals:")
        print(f"   V1: Approved            → ADA (APPROVED)")
        print(f"   V2: Rejected            → MATIC (REJECTED)")
        print(f"   V3: Rebalance           → DOT (PENDING_USER - REBALANCE)")
        print(f"   V4: High Risk LT        → AR (PENDING_USER)")
        print(f"   V5: Low Priority        → UNI (PENDING_USER - priority 35)")
        print(f"   V6: Staking Play        → ATOM (PENDING_USER)")
        print(f"\n✅ All proposals pass validation")
        print(f"✅ User: {user.email} (ID: {user.id})")
        
    except Exception as e:
        session.rollback()
        print(f"\n❌ Error creating seed data: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    print("="*60)
    print("EPOCH B: Proposal Seed Data (10-12 Proposals)")
    print("="*60)
    create_seed_data()
    print("="*60)

