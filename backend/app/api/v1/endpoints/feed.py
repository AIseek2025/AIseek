from typing import List, Optional

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import get_read_db
from app.api.v1.endpoints.posts import PostOut
from app.services.feed_service import get_feed as get_feed_service


router = APIRouter()


@router.get("/feed", response_model=List[PostOut])
def get_feed(
    response: Response,
    category: Optional[str] = None,
    user_id: Optional[int] = None,
    limit: int = 20,
    cursor: Optional[str] = None,
    db: Session = Depends(get_read_db),
):
    """
    Get personalized feed.
    """
    res = get_feed_service(db, category=category, user_id=user_id, limit=limit, cursor=cursor)
    if res.next_cursor:
        response.headers["x-next-cursor"] = res.next_cursor
    if res.ab_variant:
        response.headers["x-ab-variant"] = res.ab_variant
    return res.items
