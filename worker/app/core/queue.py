import queue
import threading
import logging

logger = logging.getLogger(__name__)

class JobQueue:
    def __init__(self):
        self._queue = queue.Queue()
        self._jobs = {}  # Store job details (id -> status)
        self._lock = threading.Lock()

    def add_job(self, job_data: dict):
        """Add a job to the queue."""
        job_id = job_data.get("job_id")
        if not job_id:
            raise ValueError("Job ID is required")
        
        with self._lock:
            if job_id in self._jobs:
                logger.warning(f"Job {job_id} already exists in queue.")
                return False
            
            self._jobs[job_id] = {
                "status": "queued",
                "data": job_data,
                "error": None
            }
        
        self._queue.put(job_data)
        logger.info(f"Job {job_id} added to queue.")
        return True

    def get_job(self):
        """Get the next job from the queue (blocking)."""
        return self._queue.get()

    def update_status(self, job_id: str, status: str, error: str = None):
        """Update the status of a job."""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = status
                if error:
                    self._jobs[job_id]["error"] = error
                logger.info(f"Job {job_id} status updated to {status}")

    def get_status(self, job_id: str):
        """Get the status of a job."""
        with self._lock:
            return self._jobs.get(job_id)

    def task_done(self):
        """Mark a task as done."""
        self._queue.task_done()

# Global instance
job_queue = JobQueue()
