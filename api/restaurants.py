"""
Restaurant API endpoints.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from models.restaurant import Restaurant
from schemas.restaurant import (
    RestaurantDetailResponse,
    RestaurantRecommendResponse
)
from services.tag_service import generate_tags_from_restaurant
from services.recommend_service import find_similar_restaurants

router = APIRouter(prefix="/restaurants", tags=["restaurants"])


@router.get("/{place_id}", response_model=RestaurantDetailResponse)
def get_restaurant(place_id: str, db: Session = Depends(get_db)):
    """
    Get restaurant details by place_id.
    
    Returns restaurant information with generated tags.
    """
    restaurant = db.query(Restaurant).filter(Restaurant.place_id == place_id).first()
    
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Restaurant with place_id {place_id} not found"
        )
    
    # Generate tags from sentiment scores
    generated_tags = generate_tags_from_restaurant(restaurant)
    
    return RestaurantDetailResponse(
        place_id=restaurant.place_id,
        name=restaurant.name,
        grid=restaurant.grid,
        address=restaurant.address,
        rating=restaurant.rating,
        user_ratings_total=restaurant.user_ratings_total,
        primaryType=restaurant.primaryType,
        district=restaurant.district,
        generated_tags=generated_tags
    )


@router.get("/{place_id}/recommend", response_model=List[RestaurantRecommendResponse])
def recommend_restaurants(
    place_id: str,
    db: Session = Depends(get_db)
):
    """
    Get similar restaurant recommendations based on the source restaurant.
    
    Uses priority queue approach to find restaurants similar to the source:
    1. Same grid + Same type + Similar top attributes
    2. Same district + Same type + Similar top attributes
    3. Same grid + Similar top attributes
    4. Same district + Similar top attributes
    """
    # Find source restaurant
    source_restaurant = db.query(Restaurant).filter(
        Restaurant.place_id == place_id
    ).first()
    
    if not source_restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Restaurant with place_id {place_id} not found"
        )
    
    # Find similar restaurants
    similar = find_similar_restaurants(db, source_restaurant, limit=5)
    
    # Build response
    results = []
    for restaurant, match_reason in similar:
        generated_tags = generate_tags_from_restaurant(restaurant)
        results.append(RestaurantRecommendResponse(
            place_id=restaurant.place_id,
            name=restaurant.name,
            grid=restaurant.grid,
            address=restaurant.address,
            rating=restaurant.rating,
            user_ratings_total=restaurant.user_ratings_total,
            primaryType=restaurant.primaryType,
            district=restaurant.district,
            generated_tags=generated_tags,
            match_reason=match_reason
        ))
    
    return results
