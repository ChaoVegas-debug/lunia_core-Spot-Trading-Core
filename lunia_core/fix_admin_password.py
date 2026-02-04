import sys
import logging
from lunia_core.app.services.api.flask_app import app
from lunia_core.app.services.auth.database import get_session
from lunia_core.app.services.auth.models import User
from lunia_core.app.services.auth.security import hash_password

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_admin():
    with app.app_context():
        with get_session() as session:
            user = session.query(User).filter_by(email="admin@lunia.com").first()
            if user:
                logger.info(f"Found admin user: {user.email}")
                user.password_hash = hash_password("admin123")
                session.commit()
                logger.info("Password updated to 'admin123'")
            else:
                logger.error("Admin user not found!")

if __name__ == "__main__":
    fix_admin()
