import sys
import os
import logging
from sqlalchemy import create_engine, text
from alembic.config import Config
from alembic import command

# Add current directory to path so we can import app
sys.path.append(os.getcwd())

try:
    from app.core.config import get_settings
except ImportError:
    # Fallback if run from backend/
    sys.path.append(os.path.join(os.getcwd(), "app"))
    from app.core.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_migration():
    settings = get_settings()
    url = settings.DATABASE_URL
    if not url:
        logger.error("DATABASE_URL not set in environment")
        return

    logger.info(f"Connecting to DB...")
    try:
        engine = create_engine(url)
        
        # Check if reputation_score exists
        with engine.connect() as conn:
            logger.info("Checking for 'reputation_score' column in 'users' table...")
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='reputation_score'"))
            exists = result.fetchone()
            
            if exists:
                logger.info("Column 'reputation_score' ALREADY EXISTS.")
                
                # Check alembic version
                try:
                    # check if alembic_version table exists
                    has_ver_table = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_name='alembic_version'")).fetchone()
                    if has_ver_table:
                        res = conn.execute(text("SELECT version_num FROM alembic_version"))
                        version = res.scalar()
                        logger.info(f"Current alembic version: {version}")
                        
                        target_rev = "0017_user_reputation"
                        # If version is older or different (and we know column exists), we might need to stamp
                        # But be careful not to stamp if it's actually NEWER (though unlikely here)
                        
                        if version != target_rev:
                            logger.info(f"Version mismatch (current: {version}, target: {target_rev}). Since column exists, attempting to STAMP head...")
                            alembic_cfg = Config("alembic.ini")
                            alembic_cfg.set_main_option("script_location", "alembic")
                            alembic_cfg.set_main_option("sqlalchemy.url", url)
                            command.stamp(alembic_cfg, "head")
                            logger.info("Stamped 'head' successfully.")
                    else:
                         logger.info("alembic_version table missing. Stamping head...")
                         alembic_cfg = Config("alembic.ini")
                         alembic_cfg.set_main_option("script_location", "alembic")
                         alembic_cfg.set_main_option("sqlalchemy.url", url)
                         command.stamp(alembic_cfg, "head")
                except Exception as e:
                    logger.warning(f"Could not check/stamp alembic version: {e}")
            else:
                logger.info("Column 'reputation_score' MISSING. Running migrations...")
                alembic_cfg = Config("alembic.ini")
                alembic_cfg.set_main_option("script_location", "alembic")
                alembic_cfg.set_main_option("sqlalchemy.url", url)
                try:
                    command.upgrade(alembic_cfg, "head")
                    logger.info("Migration run successfully.")
                except Exception as e:
                    logger.error(f"Migration FAILED: {e}")
                    raise e
                
    except Exception as e:
        logger.error(f"Error checking/migrating DB: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_migration()
