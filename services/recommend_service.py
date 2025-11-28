"""
Restaurant recommendation service.
Implements priority-based similar restaurant search.
"""
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_

from models.restaurant import Restaurant
from core.config import settings


# Attribute to column mapping
ATTR_TO_COLUMN = {
    "food": Restaurant.S_food_avg,
    "service": Restaurant.S_service_avg,
    "ambience": Restaurant.S_ambience_avg,
    "price": Restaurant.S_price_avg,
    "hygiene": Restaurant.S_hygiene_avg,
    "waiting": Restaurant.S_waiting_avg,
    "accessibility": Restaurant.S_accessibility_avg
}


def get_top_attributes(restaurant: Restaurant, min_threshold: float, max_count: int = 2) -> List[str]:
    """
    Get top attributes from a restaurant based on sentiment scores.
    
    Args:
        restaurant: Source restaurant
        min_threshold: Minimum score threshold
        max_count: Maximum number of attributes to return
        
    Returns:
        List of top attribute names
    """
    scores = restaurant.get_sentiment_scores()
    
    # Filter and sort by score
    valid_scores = [
        (attr, score) for attr, score in scores.items() 
        if score is not None and score >= min_threshold
    ]
    valid_scores.sort(key=lambda x: x[1], reverse=True)
    
    return [attr for attr, _ in valid_scores[:max_count]]


def find_similar_restaurants(
    db: Session,
    source_restaurant: Restaurant,
    limit: int = 5
) -> List[Tuple[Restaurant, str]]:
    """
    Find similar restaurants using priority queue approach.
    
    Priority order:
    1. Same grid + Same type + High attribute scores
    2. Same district + Same type + High attribute scores
    3. Same grid + High attribute scores (any type)
    4. Same district + High attribute scores (any type)
    
    Args:
        db: Database session
        source_restaurant: Source restaurant to find similar ones for
        limit: Maximum number of restaurants to return
        
    Returns:
        List of (Restaurant, match_reason) tuples
    """
    min_threshold = settings.MIN_SCORE_THRESHOLD
    results: List[Tuple[Restaurant, str]] = []
    found_ids = {source_restaurant.place_id}  # Exclude source restaurant
    
    # Get top attributes from source restaurant
    top_attrs = get_top_attributes(source_restaurant, min_threshold, max_count=2)
    
    # If no attributes meet threshold, use fallback with just location/type matching
    if not top_attrs:
        return _fallback_recommendations(db, source_restaurant, limit, found_ids)
    
    # Build attribute score conditions
    attr_conditions = []
    for attr in top_attrs:
        col = ATTR_TO_COLUMN.get(attr)
        if col is not None:
            attr_conditions.append(col >= min_threshold)
    
    # Priority 1: grid + primaryType + attributes
    if len(results) < limit and source_restaurant.grid and source_restaurant.primaryType:
        priority1 = db.query(Restaurant).filter(
            and_(
                Restaurant.place_id.notin_(found_ids),
                Restaurant.grid == source_restaurant.grid,
                Restaurant.primaryType == source_restaurant.primaryType,
                *attr_conditions
            )
        ).order_by(Restaurant.rating.desc()).limit(limit - len(results)).all()
        
        for r in priority1:
            if len(results) >= limit:
                break
            results.append((r, "같은 지역(grid) + 같은 타입 + 유사한 강점"))
            found_ids.add(r.place_id)
    
    # Priority 2: district + primaryType + attributes
    if len(results) < limit and source_restaurant.primaryType:
        priority2 = db.query(Restaurant).filter(
            and_(
                Restaurant.place_id.notin_(found_ids),
                Restaurant.district == source_restaurant.district,
                Restaurant.primaryType == source_restaurant.primaryType,
                *attr_conditions
            )
        ).order_by(Restaurant.rating.desc()).limit(limit - len(results)).all()
        
        for r in priority2:
            if len(results) >= limit:
                break
            results.append((r, "같은 구역(district) + 같은 타입 + 유사한 강점"))
            found_ids.add(r.place_id)
    
    # Priority 3: grid + attributes (any type)
    if len(results) < limit and source_restaurant.grid:
        priority3 = db.query(Restaurant).filter(
            and_(
                Restaurant.place_id.notin_(found_ids),
                Restaurant.grid == source_restaurant.grid,
                *attr_conditions
            )
        ).order_by(Restaurant.rating.desc()).limit(limit - len(results)).all()
        
        for r in priority3:
            if len(results) >= limit:
                break
            results.append((r, "같은 지역(grid) + 유사한 강점"))
            found_ids.add(r.place_id)
    
    # Priority 4: district + attributes (any type)
    if len(results) < limit:
        priority4 = db.query(Restaurant).filter(
            and_(
                Restaurant.place_id.notin_(found_ids),
                Restaurant.district == source_restaurant.district,
                *attr_conditions
            )
        ).order_by(Restaurant.rating.desc()).limit(limit - len(results)).all()
        
        for r in priority4:
            if len(results) >= limit:
                break
            results.append((r, "같은 구역(district) + 유사한 강점"))
            found_ids.add(r.place_id)
    
    # If still need more, fall back to basic matching
    if len(results) < limit:
        fallback = _fallback_recommendations(db, source_restaurant, limit - len(results), found_ids)
        results.extend(fallback)
    
    return results


def _fallback_recommendations(
    db: Session,
    source: Restaurant,
    limit: int,
    exclude_ids: set
) -> List[Tuple[Restaurant, str]]:
    """
    Fallback recommendations when no attribute-based matches are found.
    Uses location and type matching only.
    
    Args:
        db: Database session
        source: Source restaurant
        limit: Number of recommendations to return
        exclude_ids: Set of place_ids to exclude
        
    Returns:
        List of (Restaurant, match_reason) tuples
    """
    results = []
    
    # Try same district and type first
    if source.primaryType:
        fallback1 = db.query(Restaurant).filter(
            and_(
                Restaurant.place_id.notin_(exclude_ids),
                Restaurant.district == source.district,
                Restaurant.primaryType == source.primaryType
            )
        ).order_by(Restaurant.rating.desc()).limit(limit).all()
        
        for r in fallback1:
            if len(results) >= limit:
                break
            results.append((r, "같은 구역(district) + 같은 타입"))
            exclude_ids.add(r.place_id)
    
    # Then just same district
    if len(results) < limit:
        fallback2 = db.query(Restaurant).filter(
            and_(
                Restaurant.place_id.notin_(exclude_ids),
                Restaurant.district == source.district
            )
        ).order_by(Restaurant.rating.desc()).limit(limit - len(results)).all()
        
        for r in fallback2:
            if len(results) >= limit:
                break
            results.append((r, "같은 구역(district)"))
            exclude_ids.add(r.place_id)
    
    return results
