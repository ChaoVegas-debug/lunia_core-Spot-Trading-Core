
import sys
import os

# Add path to find app
sys.path.append(os.path.join(os.getcwd(), "lunia_core"))

from app.services.api.flask_app import app, get_session
from app.services.auth.auth import get_user_by_email, create_user

def seed_trader():
    with app.app_context():
        session = get_session()
        email = "trader@example.com"
        password = "trader123"
        
        user = get_user_by_email(session, email)
        if user:
            print(f"User {email} already exists.")
            # Verify password? Can't easily hash check without login attempt.
            # Assuming it's fine or we reset it (if we had reset logic).
            # For now, just report existence.
        else:
            print(f"Creating user {email}...")
            create_user(session, email, password, role="TRADER")
            print("User created.")
        
if __name__ == "__main__":
    seed_trader()
