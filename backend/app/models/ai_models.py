from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.sql import func
from app.db.base_class import Base

class AIJob(Base):
    __tablename__ = "ai_jobs"

    id = Column(String, primary_key=True, index=True) # UUID
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    status = Column(String, default="queued", index=True) # queued, running, completed, failed, needs_review
    
    # Input
    input_text = Column(Text, nullable=True) # Long text
    prompt = Column(Text, nullable=True) # User instructions
    
    # Output
    result_video_url = Column(String, nullable=True)
    result_cover_url = Column(String, nullable=True)
    
    # QC
    qc_score = Column(Integer, nullable=True)
    qc_status = Column(String, nullable=True) # pass, block, manual_review
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
