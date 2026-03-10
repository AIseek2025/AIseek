from app.db.session import SessionLocal
from app.models.all_models import Post, AIJob
import json

db = SessionLocal()
print("--- Checking Posts ---")
posts = db.query(Post).order_by(Post.id.desc()).limit(5).all()
for p in posts:
    print(f"Post {p.id}: user_id={p.user_id}, status={p.status}, video_url={p.video_url}, active_media={p.active_media_asset_id}")
    if p.active_media_asset_id:
        print(f"  Media Asset ID: {p.active_media_asset_id}")

print("\n--- Checking Jobs ---")
# AIJob might not have updated_at, check fields
jobs = db.query(AIJob).limit(5).all()
for j in jobs:
    print(f"Job {j.id}: post_id={j.post_id}, status={j.status}, progress={j.progress}, error={j.error}")
