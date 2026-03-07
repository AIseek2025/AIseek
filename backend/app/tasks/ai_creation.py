from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.all_models import AIJob
from app.services.ai_pipeline import ai_pipeline


@celery_app.task(bind=True)
def run_ai_pipeline(self, job_id: str, payload: dict) -> dict:
    db = SessionLocal()
    try:
        job = db.query(AIJob).filter(AIJob.id == job_id).first()
        if not job:
            job = AIJob(id=job_id, user_id=int(payload.get("user_id") or 0), status="processing", progress=0)
            db.add(job)
            db.commit()
        else:
            job.status = "processing"
            job.progress = 0
            db.commit()

        result = ai_pipeline.process_job(job_id, payload)
        job.status = "completed"
        job.progress = 100
        job.result_json = result
        db.commit()
        return result
    except Exception as e:
        try:
            job = db.query(AIJob).filter(AIJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error = str(e)
                db.commit()
        except Exception:
            pass
        raise
    finally:
        try:
            db.close()
        except Exception:
            pass
