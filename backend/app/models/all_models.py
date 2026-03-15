from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    phone = Column(String, unique=True, index=True, nullable=True)
    password_hash = Column(String, nullable=False)
    
    # Profile
    nickname = Column(String, index=True)
    avatar = Column(String, nullable=True)
    background = Column(String, nullable=True)
    bio = Column(String, nullable=True)
    gender = Column(String, nullable=True)  # 'male', 'female', 'other'
    birthday = Column(String, nullable=True) # Changed to String for simplicity in MVP (YYYY-MM-DD)
    location = Column(String, nullable=True)
    aiseek_id = Column(String, unique=True, index=True)  # Unique ID like TikTok ID
    
    # Stats
    followers_count = Column(Integer, default=0)
    following_count = Column(Integer, default=0)
    likes_received_count = Column(Integer, default=0)
    
    # Settings
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    settings = Column(JSON, default={})  # Privacy, notifications, etc.
    reputation_score = Column(Integer, default=100)
    reputation_updated_at = Column(DateTime(timezone=True), nullable=True)
    submit_banned_until = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    posts = relationship("Post", back_populates="owner")
    comments = relationship("Comment", back_populates="author")
    persona = relationship("UserPersona", uselist=False, back_populates="user")

class UserPersona(Base):
    """AI User Profile/Persona for personalized recommendations."""
    __tablename__ = "user_personas"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    
    # Tags extracted from user behavior (e.g., ["tech", "coding", "cats"])
    tags = Column(JSON, default=[])
    
    # Vector representation of interests (for vector search/matching)
    interest_vector = Column(JSON, nullable=True) 
    
    # Log of recent behaviors for AI analysis (e.g., [{"action": "like", "category": "tech", "timestamp": ...}])
    behavior_log = Column(JSON, default=[])
    
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    user = relationship("User", back_populates="persona")

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    summary = Column(Text, nullable=True)
    video_desc = Column(Text, nullable=True)  # 视频介绍，展示在视频页右下方用户名下方
    
    # Category for "Featured" section
    # e.g., "AI", "Programming", "Ecommerce", "Marketing", "Multimodal", "Robots"
    category = Column(String, index=True, nullable=True)
    
    # Type: 'video' or 'image_text'
    post_type = Column(String, default="video", index=True)
    
    # Content URLs
    video_url = Column(String, nullable=True) # For video posts
    images = Column(JSON, nullable=True)      # For image_text posts: ["url1", "url2", ...]
    cover_url = Column(String, nullable=True)
    source_key = Column(String, nullable=True, index=True)
    source_url = Column(String, nullable=True)
    processed_url = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    status_updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    video_width = Column(Integer, nullable=True)
    video_height = Column(Integer, nullable=True)
    active_media_asset_id = Column(Integer, ForeignKey("media_assets.id"), nullable=True, index=True)
    ai_job_id = Column(String, nullable=True, index=True)
    
    # User Custom Instructions
    custom_instructions = Column(Text, nullable=True)
    
    duration = Column(Integer, nullable=True)  # Seconds
    
    # Content
    content_text = Column(Text, nullable=True)  # Original text
    status = Column(String, default="processing")  # queued, processing, done, failed
    
    # Stats
    views_count = Column(Integer, default=0)
    likes_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)
    favorites_count = Column(Integer, default=0)
    shares_count = Column(Integer, default=0)
    downloads_count = Column(Integer, default=0)

    download_enabled = Column(Boolean, default=True, index=True)
    
    user_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="posts")
    media_assets = relationship("MediaAsset", back_populates="post", foreign_keys="MediaAsset.post_id", cascade="all, delete-orphan", order_by="desc(MediaAsset.created_at)")
    active_media_asset = relationship("MediaAsset", foreign_keys=[active_media_asset_id], uselist=False)
    
    danmaku = relationship("Danmaku", back_populates="post")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    version = Column(String, nullable=False, index=True)

    hls_url = Column(String, nullable=True)
    mp4_url = Column(String, nullable=True)
    cover_url = Column(String, nullable=True)
    subtitle_tracks = Column(JSON, nullable=True)
    background_audit = Column(JSON, nullable=True)

    duration = Column(Integer, nullable=True)
    video_width = Column(Integer, nullable=True)
    video_height = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    post = relationship("Post", back_populates="media_assets", foreign_keys=[post_id])

class Comment(Base):
    __tablename__ = "comments"
    
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    
    user_id = Column(Integer, ForeignKey("users.id"))
    post_id = Column(Integer, ForeignKey("posts.id"))
    parent_id = Column(Integer, ForeignKey("comments.id"), nullable=True)  # Threaded comments
    
    author = relationship("User", back_populates="comments")
    replies = relationship("Comment")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class CommentReaction(Base):
    __tablename__ = "comment_reactions"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    comment_id = Column(Integer, ForeignKey("comments.id"), primary_key=True)
    reaction = Column(String, nullable=False)  # like | dislike
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Interaction(Base):
    __tablename__ = "interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    post_id = Column(Integer, ForeignKey("posts.id"))
    type = Column(String, nullable=False)  # like, favorite, share
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Follow(Base):
    __tablename__ = "follows"
    
    follower_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    following_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"))
    receiver_id = Column(Integer, ForeignKey("users.id"))
    content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Danmaku(Base):
    """Bullet comments on videos."""
    __tablename__ = "danmaku"
    
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True) # Can be anonymous? For now link to user
    
    content = Column(String, nullable=False)
    timestamp = Column(Float, nullable=False) # Time in video (seconds)
    color = Column(String, default="#FFFFFF")
    position = Column(Integer, default=0) # 0: scroll, 1: top, 2: bottom
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    post = relationship("Post", back_populates="danmaku")

class FriendRequest(Base):
    __tablename__ = "friend_requests"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"))
    receiver_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="pending") # pending, accepted, rejected
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class NotificationEvent(Base):
    __tablename__ = "notification_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    event_type = Column(String, index=True, nullable=False)
    event_key = Column(String, unique=True, index=True, nullable=False)
    payload = Column(JSON, nullable=False, default={})
    created_at_ts = Column(Float, index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class NotificationRead(Base):
    __tablename__ = "notification_reads"

    user_id = Column(Integer, primary_key=True)
    last_read_ts = Column(Float, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ClientEvent(Base):
    __tablename__ = "client_events"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=True)
    user_id = Column(Integer, index=True, nullable=True)
    name = Column(String, index=True, nullable=False)
    ts = Column(Float, index=True, nullable=False)
    tab = Column(String, nullable=True)
    route = Column(String, nullable=True)
    request_id = Column(String, nullable=True)
    data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ESReindexJob(Base):
    __tablename__ = "es_reindex_jobs"

    id = Column(String, primary_key=True, index=True)
    alias = Column(String, index=True, nullable=True)
    status = Column(String, index=True, nullable=True)
    new_index = Column(String, index=True, nullable=True)
    ok = Column(Integer, default=0)
    total = Column(Integer, default=0)
    cancelled = Column(Boolean, default=False)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ABAssignment(Base):
    __tablename__ = "ab_assignments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    experiment = Column(String, index=True, nullable=False)
    variant = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PostCounterEvent(Base):
    __tablename__ = "post_counter_events"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, index=True, nullable=False)
    counter = Column(String, index=True, nullable=False)
    delta = Column(Integer, nullable=False)
    event_key = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PostCounter(Base):
    __tablename__ = "post_counters"

    post_id = Column(Integer, primary_key=True)
    likes_count = Column(Integer, default=0)
    favorites_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AIJob(Base):
    __tablename__ = "ai_jobs"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    post_id = Column(Integer, nullable=True, index=True)
    kind = Column(String, nullable=True, index=True)
    status = Column(String, default="queued", index=True)
    progress = Column(Integer, default=0)
    stage = Column(String, nullable=True, index=True)
    stage_message = Column(Text, nullable=True)
    input_json = Column(JSON, nullable=True)
    draft_json = Column(JSON, nullable=True)
    worker_task_id = Column(String, nullable=True, index=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    dispatch_attempts = Column(Integer, default=0)
    last_dispatch_at = Column(DateTime(timezone=True), nullable=True)
    next_dispatch_at = Column(DateTime(timezone=True), nullable=True)
    result_json = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AIModerationCheck(Base):
    __tablename__ = "ai_moderation_checks"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, index=True, nullable=False)
    user_id = Column(Integer, index=True, nullable=False)
    post_id = Column(Integer, index=True, nullable=True)
    status = Column(String, default="pending", index=True)
    reasons = Column(JSON, nullable=True)
    appeal = Column(JSON, nullable=True)
    decision_note = Column(Text, nullable=True)
    decided_by = Column(Integer, nullable=True, index=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserReputationEvent(Base):
    __tablename__ = "user_reputation_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    post_id = Column(Integer, index=True, nullable=True)
    delta = Column(Integer, nullable=False)
    score_after = Column(Integer, nullable=False)
    reasons = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AIJobMessage(Base):
    __tablename__ = "ai_job_messages"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, index=True, nullable=False)
    user_id = Column(Integer, index=True, nullable=False)
    role = Column(String, index=True, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AIJobDraftVersion(Base):
    __tablename__ = "ai_job_draft_versions"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, index=True, nullable=False)
    user_id = Column(Integer, index=True, nullable=False)
    source = Column(String, index=True, nullable=True)
    draft_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
