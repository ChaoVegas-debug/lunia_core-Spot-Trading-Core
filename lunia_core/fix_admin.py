import sys
import os

# Add current dir to path to find app module
sys.path.append(os.getcwd())

from app.services.auth.database import get_session, init_db, engine, Base
from app.services.auth.security import get_user_by_email, hash_password
from app.services.auth.users import create_user
from app.core.state import set_state 

def fix_users():
    print("Initializing DB...")
    init_db(lambda: Base.metadata.create_all(bind=engine))
    
    with get_session() as session:
        # 1. FIX ADMIN
        admin_email = "admin@lunia.com"
        print(f"Checking {admin_email}...")
        admin = get_user_by_email(session, admin_email)
        
        if admin:
            print("Admin exists. resetting password to 'admin'")
            admin.password_hash = hash_password("admin")
            admin.role = "ADMIN"
            # tier/is_onboarded do not exist on User model
            session.add(admin)
        else:
            print("Creating Admin user...")
            create_user(session, email=admin_email, password="admin", role="ADMIN")

        # 2. FIX TRADER
        trader_email = "trader@example.com"
        trader = get_user_by_email(session, trader_email)
        if trader:
            trader.role = "TRADER"
            session.add(trader)
        
        session.commit()
        print("DB Users Updated.")

    # 3. SEED STATE (Bypass Onboarding)
    print("Seeding State...")
    set_state({
        "exchanges": {
            "binance": {
                "id": "binance", 
                "name": "Binance Spot",
                "enabled": True, 
                "connected": True, 
                "allocation": 1.0,
                "api_key": "seeded-key",
                "risk_label": "LOW"
            }
        },
        "spot": {
            "enabled": True,
            "weights": {"scalping_breakout": 1.0}
        },
        "system_mode": "MANUAL",
        "global_stop": False
    })
    print("State Seeded.")

if __name__ == "__main__":
    fix_users()
