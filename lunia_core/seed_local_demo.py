import sys
import os
import logging
from lunia_core.app.services.api.flask_app import app
from lunia_core.app.services.auth.database import get_session
from lunia_core.app.services.auth.users import ensure_seed_admin, create_user
from lunia_core.app.services.auth.models import User
from lunia_core.app.core.state import set_state

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed():
    with app.app_context():
        # init_db is handled by app import side-effects or we can rely on it being done
        logger.info("Starting Seed...")
        
        with get_session() as session:
            # 1. Create Users
            users = [
                ("admin@example.com", "admin123", "ADMIN"),
                ("trader@example.com", "trader123", "TRADER"),
                ("fund@example.com", "fund123", "FUND"),
                ("user@example.com", "user123", "USER")
            ]
            
            for email, pwd, role_name in users:
                # Check exist
                existing = session.query(User).filter_by(email=email).first()
                if not existing:
                    create_user(session, email=email, password=pwd, role=role_name)
                    logger.info(f"Created: {email} ({role_name})")
                else:
                    logger.info(f"Exists: {email}")
            
        # 2. Seed State
        logger.info("Seeding Runtime State...")
        
        from lunia_core.app.core.portfolio.engine import PortfolioEngine
        from lunia_core.app.core.portfolio.types import PortfolioType, RiskProfile

        p1 = PortfolioEngine.generate_portfolio(PortfolioType.LONG_TERM, RiskProfile.BALANCED, 10000.0)
        p2 = PortfolioEngine.generate_portfolio(PortfolioType.TACTICAL, RiskProfile.AGGRESSIVE, 2000.0)
        
        set_state({
            "auto_mode": True,
            "global_stop": False,
            "spot": {
                "enabled": True,
                "weights": {
                    "micro_trend_scalper": 0.5,
                    "scalping_breakout": 0.3, 
                    "bollinger_reversion": 0.2
                },
                "exchanges": {
                    "binance": {"enabled": True, "allocation": 0.8},
                    "okx": {"enabled": True, "allocation": 0.2}
                }
            },
            "ops": {
                "capital": {"cap_pct": 0.5}
            },
            "portfolio": {
                "definitions": {
                    p1.id: p1.to_dict(),
                    p2.id: p2.to_dict()
                }
            }
        })
        logger.info("Done.")
        
        # Verify
        with get_session() as session:
            u = session.query(User).filter_by(email="trader@example.com").first()
            if u:
                logger.info(f"VERIFIED: {u.email} ID={u.id} Role={u.role}")
            else:
                logger.error("VERIFICATION FAILED: Trader not found")

if __name__ == "__main__":
    seed()
