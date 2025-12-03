"""
Enhanced tag generation service for restaurants.
Generates smart Korean tags based on sentiment scores and Z-scores.
"""
from typing import List, Dict, Optional
from enum import Enum

from core.config import settings


class TagLevel(Enum):
    """Tag intensity levels based on Z-score ranges."""
    EXCEPTIONAL = "exceptional"  # Z > 1.5 (top 5%)
    EXCELLENT = "excellent"      # Z > 1.0 (top 15%)
    VERY_GOOD = "very_good"      # Z > 0.5 (top 30%)
    GOOD = "good"                # Z > 0 (above average)


# Enhanced tag mappings with different intensity levels
TAG_MAPPINGS = {
    "food": {
        TagLevel.EXCEPTIONAL: "🌟 최고의 맛",
        TagLevel.EXCELLENT: "⭐ 매우 맛있는",
        TagLevel.VERY_GOOD: "맛집 인정",
        TagLevel.GOOD: "맛 좋음"
    },
    "service": {
        TagLevel.EXCEPTIONAL: "🌟 최상급 서비스",
        TagLevel.EXCELLENT: "⭐ 친절한 서비스",
        TagLevel.VERY_GOOD: "서비스 훌륭",
        TagLevel.GOOD: "서비스 좋음"
    },
    "ambience": {
        TagLevel.EXCEPTIONAL: "🌟 완벽한 분위기",
        TagLevel.EXCELLENT: "⭐ 감각적인 인테리어",
        TagLevel.VERY_GOOD: "분위기 멋짐",
        TagLevel.GOOD: "분위기 좋음"
    },
    "price": {
        TagLevel.EXCEPTIONAL: "🌟 가성비 끝판왕",
        TagLevel.EXCELLENT: "⭐ 가성비 최고",
        TagLevel.VERY_GOOD: "가성비 훌륭",
        TagLevel.GOOD: "가성비 좋음"
    },
    "hygiene": {
        TagLevel.EXCEPTIONAL: "🌟 완벽한 청결",
        TagLevel.EXCELLENT: "⭐ 매우 청결함",
        TagLevel.VERY_GOOD: "청결도 우수",
        TagLevel.GOOD: "청결함"
    },
    "waiting": {
        TagLevel.EXCEPTIONAL: "🌟 대기 없음",
        TagLevel.EXCELLENT: "⭐ 웨이팅 짧음",
        TagLevel.VERY_GOOD: "회전율 빠름",
        TagLevel.GOOD: "대기 괜찮음"
    },
    "accessibility": {
        TagLevel.EXCEPTIONAL: "🌟 접근성 완벽",
        TagLevel.EXCELLENT: "⭐ 찾아가기 쉬움",
        TagLevel.VERY_GOOD: "교통 편리",
        TagLevel.GOOD: "접근성 좋음"
    }
}


# Combination tags based on multiple aspects
COMBO_TAG_RULES = [
    {
        "name": "💎 완벽한 데이트 코스",
        "conditions": {
            "ambience": 0.8,
            "service": 0.7,
            "food": 0.7
        },
        "z_threshold": 0.5  # At least one Z-score should be > 0.5
    },
    {
        "name": "🎯 가성비 맛집",
        "conditions": {
            "price": 0.8,
            "food": 0.8
        },
        "z_threshold": 0.5
    },
    {
        "name": "👨‍👩‍👧‍👦 가족 외식 추천",
        "conditions": {
            "service": 0.7,
            "ambience": 0.6,
            "accessibility": 0.6
        },
        "z_threshold": 0.3
    },
    {
        "name": "⚡ 빠른 식사",
        "conditions": {
            "waiting": 0.8,
            "food": 0.6
        },
        "z_threshold": 0.5
    },
    {
        "name": "🏆 모든 면에서 완벽",
        "conditions": {
            "food": 0.9,
            "service": 0.9,
            "ambience": 0.8
        },
        "z_threshold": 1.0
    },
    {
        "name": "🍽️ 특별한 날 추천",
        "conditions": {
            "ambience": 0.9,
            "service": 0.8,
            "food": 0.8
        },
        "z_threshold": 0.8
    },
    {
        "name": "🌟 미슐랭급 맛",
        "conditions": {
            "food": 1.0
        },
        "z_threshold": 1.5  # Top 5% in food
    },
    {
        "name": "💰 가심비 최고",
        "conditions": {
            "price": 1.0,
            "food": 0.7,
            "service": 0.6
        },
        "z_threshold": 1.0
    }
]


def get_tag_level(z_score: float) -> Optional[TagLevel]:
    """
    Determine tag intensity level based on Z-score.
    
    Args:
        z_score: Z-score value
        
    Returns:
        TagLevel or None if below threshold
    """
    if z_score > 1.5:
        return TagLevel.EXCEPTIONAL
    elif z_score > 1.0:
        return TagLevel.EXCELLENT
    elif z_score > 0.5:
        return TagLevel.VERY_GOOD
    elif z_score > 0:
        return TagLevel.GOOD
    return None


def generate_aspect_tags(
    scores: Dict[str, Optional[float]],
    z_scores: Dict[str, Optional[float]],
    max_tags: int = 3
) -> List[str]:
    """
    Generate aspect-based tags using Z-scores for intensity levels.
    
    Args:
        scores: Regular sentiment scores (0-1 range)
        z_scores: Z-score normalized values
        max_tags: Maximum number of aspect tags to generate
        
    Returns:
        List of aspect tags
    """
    tags = []
    
    # Score each aspect and sort by Z-score
    aspect_rankings = []
    for aspect in ["food", "service", "ambience", "price", "hygiene", "waiting", "accessibility"]:
        z_score = z_scores.get(aspect)
        regular_score = scores.get(aspect)
        
        if z_score is not None and regular_score is not None:
            # Use Z-score for ranking, but require minimum regular score
            if regular_score > 0.5:  # Basic threshold
                level = get_tag_level(z_score)
                if level:
                    aspect_rankings.append((aspect, z_score, level))
    
    # Sort by Z-score (highest first)
    aspect_rankings.sort(key=lambda x: x[1], reverse=True)
    
    # Generate tags for top aspects
    for aspect, z_score, level in aspect_rankings[:max_tags]:
        tag = TAG_MAPPINGS[aspect][level]
        tags.append(tag)
    
    return tags


def generate_combo_tags(
    scores: Dict[str, Optional[float]],
    z_scores: Dict[str, Optional[float]]
) -> List[str]:
    """
    Generate combination tags based on multiple aspects.
    
    Args:
        scores: Regular sentiment scores
        z_scores: Z-score normalized values
        
    Returns:
        List of combination tags
    """
    combo_tags = []
    
    for rule in COMBO_TAG_RULES:
        # Check if all conditions are met
        conditions_met = True
        max_z = 0
        
        for aspect, min_score in rule["conditions"].items():
            score = scores.get(aspect)
            z_score = z_scores.get(aspect, -999)
            
            if score is None or score < min_score:
                conditions_met = False
                break
            
            max_z = max(max_z, z_score)
        
        # Also check if at least one Z-score meets threshold
        if conditions_met and max_z >= rule["z_threshold"]:
            combo_tags.append(rule["name"])
    
    return combo_tags


def generate_tags_from_scores(
    scores: Dict[str, Optional[float]],
    z_scores: Optional[Dict[str, Optional[float]]] = None,
    max_total_tags: int = 5,
    include_combo: bool = True
) -> List[str]:
    """
    Generate enhanced Korean tags from sentiment scores and Z-scores.
    
    Args:
        scores: Dictionary of attribute names to sentiment scores (0-1 range)
        z_scores: Dictionary of attribute names to Z-scores (normalized)
        max_total_tags: Maximum number of total tags
        include_combo: Whether to include combination tags
        
    Returns:
        List of Korean tags
        
    Example:
        scores = {"food": 0.9, "service": 0.8, "ambience": 0.7, "price": 0.9}
        z_scores = {"food": 1.6, "service": 0.8, "ambience": 0.5, "price": 1.2}
        Returns: ["🌟 최고의 맛", "⭐ 가성비 최고", "🎯 가성비 맛집", "서비스 훌륭"]
    """
    all_tags = []
    
    # If no Z-scores provided, fall back to simple threshold-based tags
    if z_scores is None:
        return generate_simple_tags(scores, max_total_tags)
    
    # 1. Generate combination tags first (they're special)
    if include_combo:
        combo_tags = generate_combo_tags(scores, z_scores)
        all_tags.extend(combo_tags[:2])  # Max 2 combo tags
    
    # 2. Generate aspect tags
    remaining_slots = max_total_tags - len(all_tags)
    if remaining_slots > 0:
        aspect_tags = generate_aspect_tags(scores, z_scores, max_tags=remaining_slots)
        all_tags.extend(aspect_tags)
    
    return all_tags[:max_total_tags]


def generate_simple_tags(
    scores: Dict[str, Optional[float]],
    max_tags: int = 5,
    threshold: Optional[float] = None
) -> List[str]:
    """
    Generate simple tags without Z-scores (fallback method).
    
    Args:
        scores: Dictionary of attribute names to sentiment scores
        max_tags: Maximum number of tags
        threshold: Score threshold for tag generation
        
    Returns:
        List of Korean tags
    """
    if threshold is None:
        threshold = getattr(settings, 'TAG_THRESHOLD', 0.5)
    
    simple_mappings = {
        "food": "맛 좋음",
        "service": "서비스 좋음",
        "ambience": "분위기 좋음",
        "price": "가성비 좋음",
        "hygiene": "청결함",
        "waiting": "대기 짧음",
        "accessibility": "접근성 좋음"
    }
    
    # Sort by score
    scored_aspects = [
        (aspect, score) 
        for aspect, score in scores.items() 
        if score is not None and score > threshold
    ]
    scored_aspects.sort(key=lambda x: x[1], reverse=True)
    
    tags = []
    for aspect, score in scored_aspects[:max_tags]:
        tag = simple_mappings.get(aspect)
        if tag:
            tags.append(tag)
    
    return tags


def generate_tags_from_restaurant(restaurant, max_tags: int = 5) -> List[str]:
    """
    Generate tags from a Restaurant model instance.
    
    Args:
        restaurant: Restaurant SQLAlchemy model instance
        max_tags: Maximum number of tags to generate
        
    Returns:
        List of Korean tags
    """
    # Get regular sentiment scores
    scores = restaurant.get_sentiment_scores()
    
    # Try to get Z-scores if available
    z_scores = {}
    z_score_columns = {
        "food": "Z_S_food_avg",
        "service": "Z_S_service_avg",
        "ambience": "Z_S_ambience_avg",
        "price": "Z_S_price_avg",
        "hygiene": "Z_S_hygiene_avg",
        "waiting": "Z_S_waiting_avg",
        "accessibility": "Z_S_accessibility_avg"
    }
    
    for aspect, col_name in z_score_columns.items():
        if hasattr(restaurant, col_name):
            z_value = getattr(restaurant, col_name)
            z_scores[aspect] = z_value
    
    # Generate tags
    if z_scores:
        return generate_tags_from_scores(scores, z_scores, max_total_tags=max_tags)
    else:
        return generate_simple_tags(scores, max_tags=max_tags)


# Backwards compatibility
def generate_tags_from_scores_old(
    scores: Dict[str, Optional[float]],
    threshold: Optional[float] = None
) -> List[str]:
    """
    Legacy function for backwards compatibility.
    Uses simple threshold-based tag generation.
    
    Deprecated: Use generate_tags_from_scores() instead.
    """
    return generate_simple_tags(scores, threshold=threshold)
