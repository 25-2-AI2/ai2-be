"""
User API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from schemas.user import UserResponse, UserPreferencesUpdate, UserPreferences

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """
    Get user information by ID.
    
    Returns user email and preference tags.
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found"
        )
    
    # Build response with preference tags
    preferences = UserPreferences(
        food=user.food,
        service=user.service,
        ambience=user.ambience,
        price=user.price,
        hygiene=user.hygiene,
        waiting=user.waiting,
        accessibility=user.accessibility
    )
    
    return UserResponse(
        id=user.id,
        email=user.email,
        tags=preferences
    )


@router.patch("/{user_id}/preferences", status_code=status.HTTP_200_OK)
def update_user_preferences(
    user_id: int,
    preferences: UserPreferencesUpdate,
    db: Session = Depends(get_db)
):
    """
    Partially update user preferences.
    
    Only updates fields that are provided (not None).
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found"
        )
    
    # Get only non-None update values
    update_data = preferences.get_update_data()
    
    if not update_data:
        # No fields to update
        return {}
    
    # Apply updates
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.commit()
    
    return {}
