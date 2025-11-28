"""
Tag generation service for restaurants.
Generates Korean tags based on sentiment scores.
"""
from typing import List, Dict, Optional

from core.config import settings


# Mapping from attribute names to Korean tags
TAG_MAPPING: Dict[str, str] = {
    "food": "맛 좋음",
    "service": "서비스 좋음",
    "ambience": "분위기 좋음",
    "price": "가성비 좋음",
    "hygiene": "청결함",
    "waiting": "대기 시간 짧음",
    "accessibility": "접근성 좋음"
}


def generate_tags_from_scores(
    scores: Dict[str, Optional[float]],
    threshold: Optional[float] = None
) -> List[str]:
    """
    Generate Korean tags from sentiment scores.
    
    Args:
        scores: Dictionary of attribute names to sentiment scores.
                Expected keys: food, service, ambience, price, hygiene, waiting, accessibility
        threshold: Score threshold for tag generation (default: from settings.TAG_THRESHOLD)
                  Scores must be > threshold to generate a tag.
    
    Returns:
        List of Korean tags for attributes exceeding the threshold.
    
    Example:
        scores = {"food": 1.2, "service": 0.3, "ambience": 0.8}
        threshold = 0.5
        Returns: ["맛 좋음", "분위기 좋음"]
    """
    if threshold is None:
        threshold = settings.TAG_THRESHOLD
    
    tags = []
    for attr, score in scores.items():
        if score is not None and score > threshold:
            tag = TAG_MAPPING.get(attr)
            if tag:
                tags.append(tag)
    
    return tags


def generate_tags_from_restaurant(restaurant) -> List[str]:
    """
    Generate tags from a Restaurant model instance.
    
    Args:
        restaurant: Restaurant SQLAlchemy model instance
        
    Returns:
        List of Korean tags for the restaurant
    """
    scores = restaurant.get_sentiment_scores()
    return generate_tags_from_scores(scores)
