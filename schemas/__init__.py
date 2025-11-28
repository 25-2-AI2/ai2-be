"""Schemas module containing Pydantic request/response DTOs."""
from schemas.user import UserResponse, UserPreferencesUpdate, UserPreferences
from schemas.restaurant import (
    RestaurantBase,
    RestaurantSearchResult,
    RestaurantDetailResponse,
    RestaurantRecommendResponse
)
from schemas.chat import ChatSearchRequest, ChatSearchResponse

__all__ = [
    "UserResponse",
    "UserPreferencesUpdate",
    "UserPreferences",
    "RestaurantBase",
    "RestaurantSearchResult",
    "RestaurantDetailResponse",
    "RestaurantRecommendResponse",
    "ChatSearchRequest",
    "ChatSearchResponse"
]
