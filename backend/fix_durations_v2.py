import os
import sys
import subprocess
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

# Get DB URL from env
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Fallback for local testing if needed, though mostly intended for container usage
    DATABASE_URL = "postgresql://aiseek:aiseek_password@localhost:5432/aiseek_db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def check_and_add_column():
    print("Checking database schema...")
    try:
        inspector = inspect(engine)
        columns = [c['name'] for c in inspector.get_columns('posts')]
        if 'duration' not in columns:
            print("Column 'duration' is MISSING in 'posts' table. Adding it now...")
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE posts ADD COLUMN duration INTEGER DEFAULT 0"))
                conn.commit()
            print("Column 'duration' added successfully.")
        else:
            print("Column 'duration' already exists.")
    except Exception as e:
        print(f"Schema check failed: {e}")
        # Continue anyway, maybe it works

def probe_url(url):
    if not url:
        return None
    try:
        target_path = url
        # Handle local paths
        if url.startswith("/static/"):
            # Try /app/static first (container standard)
            p1 = f"/app{url}"
            # Try relative to current dir
            p2 = os.path.abspath(f".{url}")
            
            if os.path.exists(p1):
                target_path = p1
            elif os.path.exists(p2):
                target_path = p2
        
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            target_path,
        ]
        # Use a timeout to prevent hanging
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=15).decode().strip()
        val = float(out)
        return int(round(val))
    except Exception as e:
        return None

def fix_durations():
    db = SessionLocal()
    try:
        print("Scanning for posts with 0 duration...")
        # Use raw SQL to avoid any ORM model mismatch issues
        sql = text("SELECT id, video_url, processed_url, source_url FROM posts WHERE status='done' AND (duration IS NULL OR duration = 0)")
        result = db.execute(sql)
        posts = result.fetchall()
        
        if not posts:
            print("No posts found needing repair.")
            return

        print(f"Found {len(posts)} posts to fix.")
        count = 0
        updated_ids = []
        
        for row in posts:
            pid, v_url, p_url, s_url = row
            target = v_url or p_url or s_url
            
            if not target:
                print(f"Post {pid}: No URL found, skipping.")
                continue
                
            print(f"[{pid}] Probing: {target} ... ", end="", flush=True)
            dur = probe_url(target)
            
            if dur and dur > 0:
                print(f"OK -> {dur}s")
                update_sql = text("UPDATE posts SET duration = :dur WHERE id = :pid")
                db.execute(update_sql, {"dur": dur, "pid": pid})
                updated_ids.append(pid)
                count += 1
            else:
                print("Failed (0s or error)")
        
        if count > 0:
            db.commit()
            print(f"\nSuccess! Fixed {count} posts.")
            
            # Optional: Try to bump cache if cache is available
            try:
                from app.core.cache import cache
                print("Bumping cache keys...")
                cache.bump("feed:all")
                for pid in updated_ids:
                    cache.bump(f"post:{pid}")
            except Exception:
                print("Cache bump skipped (module not available or failed).")
        else:
            print("\nNo posts were updated.")
            
    except Exception as e:
        print(f"\nCritical Error during fix: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    check_and_add_column()
    fix_durations()
