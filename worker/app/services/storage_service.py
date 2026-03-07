import logging
import os
import shutil
from pathlib import Path

import boto3
from app.core.config import settings
from app.core.utils import retry_sync

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self):
        self.client = None
        if settings.has_r2_config:
            self.client = boto3.client(
                "s3",
                endpoint_url=settings.r2_endpoint_url,
                aws_access_key_id=settings.r2_access_key_id,
                aws_secret_access_key=settings.r2_secret_access_key,
                region_name="auto"
            )

    def upload_file(self, file_path: str, object_name: str = None, content_type: str = "video/mp4", cache_control: str = None) -> str:
        """
        Upload a file to Cloudflare R2 bucket.
        """
        if not self.client:
            try:
                src = str(file_path or "")
                if not src or not os.path.exists(src):
                    return None
                rel = str(object_name or "").strip().lstrip("/")
                if not rel:
                    rel = os.path.basename(src)
                repo_root = Path(__file__).resolve().parents[3]
                out_root = repo_root / "backend" / "static" / "worker_media"
                dst = out_root / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                return f"/static/worker_media/{rel}"
            except Exception:
                logger.warning("R2 is not configured. Skipping upload.")
                return None

        if object_name is None:
            object_name = file_path.split("/")[-1]

        logger.info(f"Uploading {file_path} to R2 bucket {settings.r2_bucket_name} as {object_name}...")
        
        def _upload():
            extra = {'ContentType': str(content_type or "application/octet-stream")}
            if cache_control:
                extra['CacheControl'] = str(cache_control)
            self.client.upload_file(
                file_path, 
                settings.r2_bucket_name, 
                object_name,
                ExtraArgs=extra
            )
            return f"{settings.r2_public_url.rstrip('/')}/{object_name}"
            
        try:
            return retry_sync(_upload, max_retries=3)
        except Exception as e:
            logger.error(f"Failed to upload file to R2: {e}")
            raise

    def presigned_get_url(self, object_name: str, expiration: int = 3600) -> str:
        if not self.client:
            return None
        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.r2_bucket_name, "Key": object_name},
                ExpiresIn=int(expiration),
            )
        except Exception:
            return None

    def download_file(self, object_name: str, dst_path: str) -> bool:
        if not self.client:
            return False
        def _dl():
            self.client.download_file(settings.r2_bucket_name, object_name, dst_path)
            return True
        try:
            return bool(retry_sync(_dl, max_retries=3))
        except Exception as e:
            logger.error(f"Failed to download file from R2: {e}")
            return False

    def upload_directory(self, dir_path: str, object_prefix: str) -> str:
        base_dir = str(dir_path or "").strip()
        if not base_dir or not os.path.isdir(base_dir):
            return None
        prefix = str(object_prefix or "").strip().lstrip("/")
        if not prefix:
            prefix = "assets"

        master = None
        try:
            mp = os.path.join(base_dir, "master.m3u8")
            if os.path.exists(mp):
                master = mp
        except Exception:
            master = None

        if not self.client:
            try:
                repo_root = Path(__file__).resolve().parents[3]
                out_root = repo_root / "backend" / "static" / "worker_media" / prefix
                out_root.mkdir(parents=True, exist_ok=True)
                for root, _dirs, files in os.walk(base_dir):
                    rel_root = os.path.relpath(root, base_dir)
                    for fn in files:
                        src = os.path.join(root, fn)
                        rel = fn if rel_root == "." else os.path.join(rel_root, fn)
                        dst = out_root / rel
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, dst)
                if os.path.exists(os.path.join(base_dir, "master.m3u8")):
                    return f"/static/worker_media/{prefix}/master.m3u8"
                return f"/static/worker_media/{prefix}"
            except Exception:
                return None

        def _upload_all():
            for root, _dirs, files in os.walk(base_dir):
                rel_root = os.path.relpath(root, base_dir)
                for fn in files:
                    src = os.path.join(root, fn)
                    rel = fn if rel_root == "." else os.path.join(rel_root, fn)
                    key = f"{prefix}/{rel}".replace("\\", "/")
                    self.upload_file(src, key, content_type="application/octet-stream")
            if master:
                return f"{settings.r2_public_url.rstrip('/')}/{prefix}/master.m3u8"
            return f"{settings.r2_public_url.rstrip('/')}/{prefix}"

        try:
            return retry_sync(_upload_all, max_retries=3)
        except Exception:
            return None

# Singleton instance
storage_service = StorageService()
