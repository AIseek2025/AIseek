import boto3
from botocore.exceptions import NoCredentialsError
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self):
        self.s3_client = None
        endpoint = str(getattr(settings, "R2_ENDPOINT_URL", "") or "").strip()
        ak = str(getattr(settings, "R2_ACCESS_KEY_ID", "") or "").strip()
        sk = str(getattr(settings, "R2_SECRET_ACCESS_KEY", "") or "").strip()
        if endpoint and ak and sk:
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=ak,
                aws_secret_access_key=sk,
                region_name="auto",
            )
        self.bucket_name = settings.R2_BUCKET_NAME
        self.public_url = settings.R2_PUBLIC_URL

    def generate_presigned_upload_url(self, object_name: str, content_type: str, expiration=3600) -> dict:
        """
        Generate a presigned URL to share with the frontend for direct upload.
        This offloads the upload traffic from the backend server.
        """
        try:
            if not self.s3_client:
                return None
            response = self.s3_client.generate_presigned_post(
                self.bucket_name,
                object_name,
                Fields={'Content-Type': content_type},
                Conditions=[
                    {'Content-Type': content_type},
                    ['content-length-range', 0, 500 * 1024 * 1024] # 500MB limit
                ],
                ExpiresIn=expiration
            )
            
            # Construct the final public URL
            final_url = f"{self.public_url.rstrip('/')}/{object_name}"
            
            return {
                "upload_url": response['url'],
                "fields": response['fields'],
                "public_url": final_url,
                "file_key": object_name
            }
        except Exception as e:
            logger.error(f"Error generating presigned URL: {e}")
            return None

    def delete_object(self, object_name: str) -> bool:
        try:
            if not self.s3_client:
                return False
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=object_name)
            return True
        except Exception as e:
            logger.error(f"Error deleting object: {e}")
            return False

    def extract_object_key(self, url: str) -> str:
        u = str(url or "").strip()
        if not u:
            return ""
        pub = str(self.public_url or "").rstrip("/")
        if pub and u.startswith(pub + "/"):
            return u[len(pub) + 1 :]
        return ""

    def generate_presigned_download_url(self, object_name: str, filename: str = None, expiration: int = 600) -> str:
        try:
            if not self.s3_client:
                return ""
            key = str(object_name or "").strip()
            if not key:
                return ""
            params = {"Bucket": self.bucket_name, "Key": key}
            fn = str(filename or "").strip()
            if fn:
                params["ResponseContentDisposition"] = f'attachment; filename="{fn}"'
            return self.s3_client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=int(expiration or 600),
            )
        except Exception as e:
            logger.error(f"Error generating presigned download URL: {e}")
            return ""

    def upload_file(self, file_path: str, object_name: str, content_type: str = None, cache_control: str = None) -> bool:
        try:
            if not self.s3_client:
                return False
            key = str(object_name or "").strip().lstrip("/")
            if not key:
                return False
            extra = {}
            ct = str(content_type or "").strip()
            cc = str(cache_control or "").strip()
            if ct:
                extra["ContentType"] = ct
            if cc:
                extra["CacheControl"] = cc
            self.s3_client.upload_file(
                str(file_path),
                self.bucket_name,
                key,
                ExtraArgs=extra or None,
            )
            return True
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return False

    def download_file(self, object_name: str, file_path: str) -> bool:
        try:
            if not self.s3_client:
                return False
            key = str(object_name or "").strip().lstrip("/")
            if not key:
                return False
            self.s3_client.download_file(self.bucket_name, key, str(file_path))
            return True
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            return False

storage_service = StorageService()
