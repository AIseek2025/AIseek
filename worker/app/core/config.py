"""
Worker Configuration (Refactored from Fusion)
Uses Pydantic Settings for centralized management and validation.
"""

from pathlib import Path
from typing import Optional, List
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

_ENV_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = _ENV_ROOT.parent
import os

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ASSETS_DIR = BASE_DIR / "assets"
OUTPUTS_DIR = BASE_DIR / "outputs"
DATA_DIR = BASE_DIR / "data"

# Ensure directories exist
for directory in [ASSETS_DIR, OUTPUTS_DIR, DATA_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Constants
PLACEHOLDER_VIDEO = ASSETS_DIR / "bg_placeholder.mp4"
DB_PATH = DATA_DIR / "aiseek.db"

# Performance & Security Constants
MAX_CONTENT_LENGTH = 15000  # Max content length
MAX_QUEUE_SIZE = 50         # Max queue size
DEFAULT_LOG_LEVEL = "INFO"  # Default log level


class Settings(BaseSettings):
    """
    Application Settings
    """
    
    model_config = SettingsConfigDict(
        env_file=(
            str(_REPO_ROOT / ".env"),
            str(_REPO_ROOT / ".env.local"),
            str(_ENV_ROOT / ".env"),
            str(_ENV_ROOT / ".env.local"),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
    
    # ========== DeepSeek API ==========
    deepseek_api_key: Optional[str] = Field(
        default="",
        description="DeepSeek API Key (optional for local stub mode)"
    )
    
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com/v1",
        description="DeepSeek API Base URL"
    )
    
    deepseek_model: str = Field(
        default="deepseek-chat",
        description="DeepSeek Model Name"
    )
    
    # ========== Cloudflare R2 (Optional) ==========
    r2_endpoint_url: Optional[str] = Field(None, description="R2 Endpoint URL")
    r2_access_key_id: Optional[str] = Field(None, description="R2 Access Key ID")
    r2_secret_access_key: Optional[str] = Field(None, description="R2 Secret Access Key")
    r2_bucket_name: Optional[str] = Field(None, description="R2 Bucket Name")
    r2_public_url: Optional[str] = Field(None, description="R2 Public URL")
    
    # ========== Security ==========
    worker_secret: Optional[str] = Field(
        default=None,
        description="Worker API Bearer Token Secret"
    )
    
    # ========== Application ==========
    app_name: str = "AIseek Worker (Trae Fusion)"
    worker_host: str = Field("0.0.0.0", description="Worker Host")
    worker_port: int = Field(8000, description="Worker Port")
    
    web_url: str = Field(
        default="http://localhost:5000",
        description="Web URL for callbacks"
    )
    
    # ========== Logging ==========
    log_level: str = Field(
        default=DEFAULT_LOG_LEVEL,
        description="Log Level: DEBUG, INFO, WARNING, ERROR"
    )
    
    # ========== CORS ==========
    cors_origins: List[str] = Field(
        default=["http://localhost:5000", "http://127.0.0.1:5000"],
        description="Allowed CORS origins"
    )
    
    # ========== FFmpeg ==========
    ffmpeg_hw_accel: str = "h264_videotoolbox"  # For Mac M3 Pro
    video_bg_mode: str = "placeholder"
    video_bg_path: Optional[str] = None
    video_bg_dir: Optional[str] = None

    placeholder_provider: str = "pixabay"
    pixabay_api_key: Optional[str] = None
    pexels_api_key: Optional[str] = None
    placeholder_cache_dir: Optional[str] = None
    placeholder_cache_max_mb: int = 1024
    placeholder_search_ttl_hours: int = 24
    placeholder_video_ttl_hours: int = 24
    placeholder_max_video_mb: int = 80
    placeholder_orientation: str = "portrait"
    placeholder_min_width: int = 1080
    placeholder_min_height: int = 1920

    cover_provider_order: List[str] = Field(default=["wanx", "openai", "frame"], description="Cover generation provider order")
    cover_wan_api_key: Optional[str] = Field(default=None, description="DashScope API key for wan2.6-t2i cover generation")
    cover_wan_base_url: str = Field(default="https://dashscope.aliyuncs.com", description="DashScope base URL")
    cover_wan_model: str = Field(default="wan2.6-t2i", description="DashScope wan model name")
    cover_openai_api_key: Optional[str] = Field(default=None, description="OpenAI Images API key for cover generation")
    cover_openai_base_url: str = Field(default="https://api.openai.com/v1", description="OpenAI Images base URL")
    cover_openai_model: str = Field(default="gpt-image-1", description="OpenAI Images model")
    cover_embed_duration_sec: float = Field(default=1.0, description="Duration of embedded cover segment")
    
    # ========== Validators ==========
    @validator("log_level")
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {', '.join(valid_levels)}")
        return v.upper()
    
    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @validator("video_bg_mode")
    def validate_video_bg_mode(cls, v):
        vv = str(v or "").strip().lower()
        if vv not in {"placeholder", "lavfi", "api"}:
            raise ValueError("video_bg_mode must be placeholder|lavfi|api")
        return vv
    
    # ========== Properties ==========
    @property
    def has_r2_config(self) -> bool:
        """Check if R2 is configured"""
        return all([
            self.r2_endpoint_url,
            self.r2_access_key_id,
            self.r2_secret_access_key,
            self.r2_bucket_name,
            self.r2_public_url
        ])
    
    @property
    def has_auth(self) -> bool:
        """Check if auth is enabled"""
        return bool(self.worker_secret)


def get_settings() -> Settings:
    try:
        return Settings()
    except Exception as e:
        print(f"❌ Configuration Load Failed: {e}")
        print("📋 Please check .env file")
        # For development, return a dummy or let it fail hard? 
        # Better to fail hard so user knows config is missing.
        raise

settings = get_settings()
