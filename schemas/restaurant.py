"""
Pydantic schemas for Restaurant-related requests and responses.
"""
from pydantic import BaseModel
from typing import Optional, List


class RestaurantBase(BaseModel):
    """Base restaurant schema with common fields."""
    place_id: str
    name: str
    rating: Optional[float] = None
    
    class Config:
        from_attributes = True


class RestaurantSearchResult(RestaurantBase):
    """Restaurant schema for search results."""
    generated_tags: List[str] = []
    score: Optional[float] = None
    korean_pattern: Optional[str] = None


class RestaurantDetailResponse(BaseModel):
    """Response schema for GET /restaurants/{place_id}."""
    place_id: str
    name: str
    grid: Optional[str] = None
    address: str
    rating: Optional[float] = None
    user_ratings_total: Optional[int] = None
    primaryType: Optional[str] = None
    district: str
    generated_tags: List[str] = []
    
    class Config:
        from_attributes = True


class RestaurantRecommendResponse(BaseModel):
    """Response schema for GET /restaurants/{place_id}/recommend."""
    place_id: str
    name: str
    grid: Optional[str] = None
    address: str
    rating: Optional[float] = None
    user_ratings_total: Optional[int] = None
    primaryType: Optional[str] = None
    district: str
    generated_tags: List[str] = []
    match_reason: Optional[str] = None  # 어떤 우선순위로 매칭됐는지
    
    class Config:
        from_attributes = True
