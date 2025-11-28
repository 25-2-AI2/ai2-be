"""
Pydantic schemas for Chat-related requests and responses.
"""
from pydantic import BaseModel
from typing import Optional, List

from schemas.user import UserPreferences
from schemas.restaurant import RestaurantSearchResult


class ChatSearchRequest(BaseModel):
    """Request schema for POST /chat/search."""
    user_id: int
    query: str
    user_preferences: Optional[UserPreferences] = None


class ChatSearchResponse(BaseModel):
    """Response schema for POST /chat/search."""
    answer: str
    restaurants: List[RestaurantSearchResult] = []
