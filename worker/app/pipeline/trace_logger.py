import json
import logging
import time
import os
from pathlib import Path
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

def safe_json_serialize(obj: Any) -> Any:
    if isinstance(obj, (datetime, Path)):
        return str(obj)
    if isinstance(obj, dict):
        return {k: safe_json_serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [safe_json_serialize(i) for i in obj]
    return obj

class TraceLogger:
    def __init__(self, job_id: str):
        self.job_id = job_id
        trace_dir = str(os.getenv("TRACE_LOG_DIR") or "/app/outputs/traces").strip()
        self.log_dir = Path(trace_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"job_{job_id}_trace.json"
        self.data = {
            "job_id": job_id,
            "start_time": datetime.now().isoformat(),
            "steps": []
        }
        self._flush()

    def log_step(self, step_name: str, status: str, details: dict = None):
        entry = {
            "step": step_name,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "details": safe_json_serialize(details or {})
        }
        self.data["steps"].append(entry)
        self._flush()
        logger.info(f"[{self.job_id}] Step {step_name}: {status}")

    def _flush(self):
        try:
            with open(self.log_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to flush trace log: {e}")

    def error(self, step_name: str, error_msg: str):
        self.log_step(step_name, "error", {"error": str(error_msg)})
