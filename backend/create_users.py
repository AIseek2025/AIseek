from app.db.session import SessionLocal, engine
from app.models.all_models import User, Base
from app.api.v1.endpoints.auth import fmt_aiseek_id

# Create tables if not exist
Base.metadata.create_all(bind=engine)

db = SessionLocal()

# Backfill AIseek IDs to deterministic, incremental format based on numeric user id
users = db.query(User).all()
for u in users:
    desired = fmt_aiseek_id(u.id)
    if u.aiseek_id != desired:
        u.aiseek_id = desired
db.commit()

# Check if user exists
user = db.query(User).filter(User.username == "testuser").first()
if not user:
    new_user = User(
        username="testuser",
        password_hash="test123_hashed",
        nickname="Test User",
        email="test@example.com",
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    new_user.aiseek_id = fmt_aiseek_id(new_user.id)
    db.commit()
    print("User 'testuser' created with password '123456'")
else:
    if not user.aiseek_id:
        user.aiseek_id = fmt_aiseek_id(user.id)
        db.commit()
    print("User 'testuser' already exists")

demo = db.query(User).filter(User.username == "demo").first()
if not demo:
    new_demo = User(
        username="demo",
        password_hash="demo123_hashed",
        nickname="Demo User",
        email="demo@example.com",
    )
    db.add(new_demo)
    db.commit()
    db.refresh(new_demo)
    new_demo.aiseek_id = fmt_aiseek_id(new_demo.id)
    db.commit()
    print("User 'demo' created with password 'demo123'")
else:
    if not demo.aiseek_id:
        demo.aiseek_id = fmt_aiseek_id(demo.id)
        db.commit()
    print("User 'demo' already exists")

# Create Admin User
admin = db.query(User).filter(User.username == "admin").first()
if not admin:
    new_admin = User(
        username="admin",
        password_hash="admin123_hashed",
        nickname="Admin User",
        is_superuser=True,
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    new_admin.aiseek_id = fmt_aiseek_id(new_admin.id)
    db.commit()
    print("User 'admin' created with password 'admin123'")
else:
    if not admin.aiseek_id:
        admin.aiseek_id = fmt_aiseek_id(admin.id)
        db.commit()
    print("User 'admin' already exists")

db.close()
