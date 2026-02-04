import sys
import os
import logging
import time
import random
from lunia_core.app.services.api.flask_app import app
from lunia_core.app.services.auth.database import get_session
from lunia_core.app.services.auth.users import ensure_seed_admin, create_user
from lunia_core.app.services.auth.models import User
from lunia_core.app.core.state import set_state, get_state
from lunia_core.app.core.portfolio.engine import PortfolioEngine
from lunia_core.app.core.portfolio.types import PortfolioType, RiskProfile, PortfolioStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_full():
    with app.app_context():
        logger.info("Starting CONTROLLED FULL SEED for Prompt 2...")
        
        # 1. Users (Idempotent)
        with get_session() as session:
            users = [
                ("admin@example.com", "admin123", "ADMIN"),
                ("trader@example.com", "trader123", "TRADER"),
                ("fund@example.com", "fund123", "FUND"),
                ("user@example.com", "user123", "USER")
            ]
            for email, pwd, role_name in users:
                existing = session.query(User).filter_by(email=email).first()
                if not existing:
                    create_user(session, email=email, password=pwd, role=role_name)
                    logger.info(f"Created User: {email}")
                else:
                    # PROMPT 5 FIX: Ensure known credentials
                    from lunia_core.app.services.auth.security import hash_password
                    existing.password_hash = hash_password(pwd)
                    session.add(existing)
                    logger.info(f"User Updated: {email}")
            
            # 1.1 Risk Limits (Idempotent)
            from lunia_core.app.services.auth.models import Limit
            from datetime import datetime
            
            default_limits = [
                ("global", "risk", "max_positions", "5"),
                ("global", "risk", "max_trade_pct", "0.20"),
                ("global", "risk", "risk_per_trade_pct", "0.01"),
                ("global", "risk", "max_symbol_exposure_pct", "0.25")
            ]
            
            for scope, subject, key, val in default_limits:
                lim = session.query(Limit).filter_by(scope=scope, subject=subject, key=key).first()
                if not lim:
                    lim = Limit(scope=scope, subject=subject, key=key, value=val, updated_at=datetime.utcnow())
                    session.add(lim)
                else:
                    lim.value = val
                    lim.updated_at = datetime.utcnow()
            session.commit()
            logger.info("Risk Limits Seeded")

        # 2. Generate Portfolios
        p1 = PortfolioEngine.generate_portfolio(PortfolioType.LONG_TERM, RiskProfile.BALANCED, 15000.0)
        p1.id = "long_term_main" # Nice ID
        p1.last_rebalanced_at = time.time() - (3 * 86400) # 3 days ago

        p2 = PortfolioEngine.generate_portfolio(PortfolioType.TACTICAL, RiskProfile.AGGRESSIVE, 5000.0)
        p2.id = "tactical_alpha"
        p2.last_rebalanced_at = time.time() - (8 * 3600) # 8 hours ago

        logger.info("Generated Portfolios")

        # 3. Construct Proposal (Mock Intelligence)
        ai_proposal = {
            "id": f"prop-{int(time.time())}",
            "type": "CAPITAL_ADJUSTMENT",
            "payload": {"cap_pct": 0.65},
            "confidence": 0.88,
            "reasoning": "Market volatility decreasing. Recommend increasing capital deployment to capture yield.",
            "risk_notes": ["Medium Volatility", "Monitor Drawdown"],
            "status": "PENDING",
            "timestamp": time.time()
        }

        # 4. Construct Full State
        state_update = {
            "auto_mode": True,
            "global_stop": False,
            "portfolio_equity": 25000.0, # Visible Equity
            
            # Capital Governance
            "ops": {
                "capital": {
                    "cap_pct": 0.50, # 50%
                    "hard_max_pct": 0.90
                }
            },
            "reserves": {
                "portfolio": 0.15,
                "arbitrage": 0.10
            },
            
            # Exchanges (Top Level)
            "exchanges": {
                "binance": {"enabled": True, "allocation": 0.7, "name": "Binance", "id": "binance", "connected": True},
                "okx": {"enabled": True, "allocation": 0.3, "name": "OKX", "id": "okx", "connected": True},
                "kraken": {"enabled": False, "allocation": 0.0, "name": "Kraken", "id": "kraken", "connected": False}
            },
            
            # Strategies
            "spot": {
                "enabled": True,
                "weights": {
                    "micro_trend_scalper": 0.40,
                    "scalping_breakout": 0.30, 
                    "bollinger_reversion": 0.30,
                    "vwap_reversion": 0.0,
                    "liquidity_snipe": 0.0
                },
                # Risk Limits (Top Level in Spot config usually, or separate Limit table? RiskWidget reads from 'spot' config as fallback or 'admin/limits' API? 
                # Checking RiskWidget: reads 'spot/risk' endpoint. Endpoint reads state['spot']. 
                "max_positions": 5,
                "max_trade_pct": 0.20,
                "risk_per_trade_pct": 0.01,
                "max_symbol_exposure_pct": 0.25,
                "max_daily_loss_pct": 0.05
            },
            
            # Portfolios
            "portfolio": {
                "definitions": {
                    p1.id: p1.to_dict(),
                    p2.id: p2.to_dict()
                }
            },
            
            # AI State
            "ai": {
                "proposals": [ai_proposal]
            }
        }
        
        set_state(state_update)
        logger.info("Runtime State Updated Successfully.")

if __name__ == "__main__":
    seed_full()
