
import os
import sys

# Ensure we can import from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lunia_core.app.services.auth.database import SessionLocal, init_db, engine
from lunia_core.app.services.auth.models import User, Base
from lunia_core.app.services.auth.security import hash_password

def create_admin():
    print("Initializing Database...")
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    
    session = SessionLocal()
    try:
        email = "admin@lunia.com"
        password = "admin123"
        
        user = session.query(User).filter(User.email == email).first()
        if user:
            print(f"User {email} already exists. Updating password/role.")
            user.password_hash = hash_password(password)
            user.role = "ADMIN"
            user.is_active = True
        else:
            print(f"Creating user {email}...")
            user = User(
                email=email,
                password_hash=hash_password(password),
                role="ADMIN",
                is_active=True
            )
            session.add(user)
        
        session.commit()
        print(f"Successfully configured {email} with role {user.role}")
    except Exception as e:
        print(f"Error: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    create_admin()
