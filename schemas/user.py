"""
Pydantic schemas for User-related requests and responses.
"""
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserPreferences(BaseModel):
    """User preference scores schema."""
    food: Optional[float] = None
    service: Optional[float] = None
    ambience: Optional[float] = None
    price: Optional[float] = None
    hygiene: Optional[float] = None
    waiting: Optional[float] = None
    accessibility: Optional[float] = None


class UserResponse(BaseModel):
    """Response schema for GET /users/{user_id}."""
    id: int
    email: EmailStr
    tags: UserPreferences
    
    class Config:
        from_attributes = True


class UserPreferencesUpdate(BaseModel):
    """Request schema for PATCH /users/{user_id}/preferences."""
    food: Optional[float] = None
    service: Optional[float] = None
    ambience: Optional[float] = None
    price: Optional[float] = None
    hygiene: Optional[float] = None
    waiting: Optional[float] = None
    accessibility: Optional[float] = None
    
    def get_update_data(self) -> dict:
        """Return only fields that are not None."""
        return {k: v for k, v in self.model_dump().items() if v is not None}
