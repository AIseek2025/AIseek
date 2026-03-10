import sys
import os
from pathlib import Path

# Setup path to import backend app
current_dir = Path(__file__).resolve().parent
backend_dir = current_dir.parent / "backend"
sys.path.append(str(backend_dir))

from app.db.session import SessionLocal
from app.models.all_models import Post
from sqlalchemy import or_
# Import the helper function we modified
from app.api.v1.endpoints.posts import _probe_local_video_duration_sec

def main():
    print("Starting duration fix...")
    db = SessionLocal()
    try:
        # Find posts with status='done' but duration is 0 or NULL
        posts = db.query(Post).filter(
            Post.status == "done", 
            or_(Post.duration == 0, Post.duration == None)
        ).all()
        
        print(f"Found {len(posts)} posts to check.")
        
        fixed_count = 0
        for p in posts:
            # Determine the best URL to probe
            url = p.video_url or p.processed_url or p.source_url
            if not url:
                print(f"[Skip] Post {p.id}: No video URL found.")
                continue
                
            print(f"[Probe] Post {p.id}: {url}...", end="", flush=True)
            duration = _probe_local_video_duration_sec(url)
            
            if duration and duration > 0:
                p.duration = int(duration)
                fixed_count += 1
                print(f" Fixed! Duration: {duration}s")
            else:
                print(" Failed to probe.")
                
        if fixed_count > 0:
            db.commit()
            print(f"\nSuccess! Fixed {fixed_count} posts.")
        else:
            print("\nDone. No changes made.")
            
    except Exception as e:
        print(f"\nError occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()
