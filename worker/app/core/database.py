"""
Database Management (Refactored from Fusion)
SQLite persistence for job tracking.
"""

import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from app.core.config import settings, DB_PATH

logger = logging.getLogger("aiseek.db")

class Database:
    """SQLite Database Manager"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()
    
    def _get_connection(self):
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return dict-like rows
        return conn

    def _init_db(self):
        """Initialize database schema."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Create jobs table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                user_id TEXT,
                content TEXT,
                status TEXT,
                title TEXT,
                summary TEXT,
                video_url TEXT,
                error TEXT,
                queue_time TIMESTAMP,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON jobs(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON jobs(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON jobs(created_at)')
            
            conn.commit()
            conn.close()
            logger.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def create_job(self, job_id: str, user_id: Optional[str], content: str) -> bool:
        """Create a new job record."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            INSERT INTO jobs (job_id, user_id, content, status, queue_time)
            VALUES (?, ?, ?, ?, ?)
            ''', (job_id, user_id, content, "queued", datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to create job {job_id}: {e}")
            return False
    
    def update_job(self, job_id: str, **kwargs) -> bool:
        """Update job status and details."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Handle timestamps automatically based on status
            if "status" in kwargs:
                if kwargs["status"] == "processing":
                    kwargs["start_time"] = datetime.now().isoformat()
                elif kwargs["status"] in ["done", "error", "failed", "completed"]:
                    # Normalize status names if needed, fusion uses "done"
                    if kwargs["status"] == "completed":
                        kwargs["status"] = "done"
                    kwargs["end_time"] = datetime.now().isoformat()
            
            # Build query
            set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
            values = list(kwargs.values())
            values.append(job_id)
            
            cursor.execute(f'''
            UPDATE jobs 
            SET {set_clause}, updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ?
            ''', values)
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to update job {job_id}: {e}")
            return False
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job details."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM jobs WHERE job_id = ?', (job_id,))
            row = cursor.fetchone()
            conn.close()
            
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            return None
    
    def get_jobs_by_user(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get jobs for a user."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT * FROM jobs 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
            ''', (user_id, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get user jobs: {e}")
            return []

    def get_jobs_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get jobs by status."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM jobs WHERE status = ? ORDER BY created_at ASC', (status,))
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get jobs by status: {e}")
            return []
            
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            stats = {}
            for status in ["queued", "processing", "done", "error"]:
                cursor.execute('SELECT COUNT(*) FROM jobs WHERE status = ?', (status,))
                stats[status] = cursor.fetchone()[0]
                
            cursor.execute('SELECT COUNT(*) FROM jobs')
            stats["total"] = cursor.fetchone()[0]
            
            conn.close()
            return stats
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}

# Global instance
db = Database(DB_PATH)
