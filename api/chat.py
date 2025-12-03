"""
Chat API endpoints.
Handles RAG-based restaurant search.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from core.database import get_db
from models.restaurant import Restaurant
from models.user import User
from schemas.chat import ChatSearchRequest, ChatSearchResponse
from schemas.restaurant import RestaurantSearchResult
from services.rag_service import search_restaurants_rag
from services.tag_service import generate_tags_from_restaurant

router = APIRouter(prefix="/chat", tags=["chat"])


def get_user_preferences_from_db(db: Session, user_id: int) -> Optional[dict]:
    """
    Fetch user preferences from database.
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        Dictionary of user preferences (0~5 scale) or None if user not found
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    return user.get_preferences()


@router.post("/search", response_model=ChatSearchResponse)
async def chat_search(request: ChatSearchRequest, db: Session = Depends(get_db)):
    """
    Search restaurants using RAG pipeline.
    
    Process:
    1. Get user preferences (from request or DB)
    2. Analyze Korean query (translate + extract filters + aspects)
    3. Perform hybrid search (BM25 + E5) with Cross-Encoder reranking
    4. Fetch restaurant details from database
    5. Generate tags for each restaurant
    6. Return with LLM-generated answer
    
    Priority Order for Preferences:
    1. Query-specific intent (from LLM analysis) - HIGHEST priority
    2. Request-provided user_preferences - If query doesn't mention aspect
    3. DB-stored user preferences - Fallback if not in request
    
    Example:
    - User has price=5.0 (wants budget) stored in DB
    - Request doesn't include user_preferences
    - Query says "가격이 비싸도 괜찮음" (expensive is ok)
    - Result: price weight becomes 0.1~0.2 (query overrides DB)
    
    Note on user_preferences scale:
    - Database stores preferences in 0~5 range
    - RAG service normalizes internally to 0~1 range
    """
    query = request.query
    
    # Step 1: Determine user preferences
    # Priority: request.user_preferences > DB preferences
    user_prefs = None
    
    if request.user_preferences:
        # Use preferences from request (already 0~5 scale)
        user_prefs = request.user_preferences.model_dump()
    else:
        # Fallback to DB preferences
        db_prefs = get_user_preferences_from_db(db, request.user_id)
        if db_prefs:
            user_prefs = db_prefs
    
    # Step 2: Perform RAG search
    # Query-extracted weights will override user_prefs for mentioned aspects
    rag_result = await search_restaurants_rag(query, user_prefs, top_k=20)
    
    # Step 3: Fetch restaurants from database and build response
    restaurants_data: List[RestaurantSearchResult] = []
    
    if rag_result.place_ids:
        restaurants = db.query(Restaurant).filter(
            Restaurant.place_id.in_(rag_result.place_ids)
        ).all()
        
        # Create a lookup dict for ordering
        place_id_to_restaurant = {r.place_id: r for r in restaurants}
        
        # Build response maintaining the order from rag_result
        for i, place_id in enumerate(rag_result.place_ids):
            restaurant = place_id_to_restaurant.get(place_id)
            if not restaurant:
                continue
            
            # Generate tags
            generated_tags = generate_tags_from_restaurant(restaurant)
            
            # Get score and pattern
            score = rag_result.scores[i] if i < len(rag_result.scores) else None
            korean_pattern = rag_result.korean_patterns.get(place_id)
            pattern_source = rag_result.pattern_sources.get(place_id)
            
            # Add pattern source indicator to pattern if available
            if korean_pattern and pattern_source:
                if pattern_source == "korean":
                    korean_pattern = f"[한국인 리뷰] {korean_pattern}"
                elif pattern_source == "non_korean":
                    korean_pattern = f"[현지인 리뷰] {korean_pattern}"
            
            restaurants_data.append(RestaurantSearchResult(
                place_id=restaurant.place_id,
                name=restaurant.name,
                rating=restaurant.rating,
                generated_tags=generated_tags,
                score=score,
                korean_pattern=korean_pattern
            ))
    
    return ChatSearchResponse(
        answer=rag_result.answer,
        restaurants=restaurants_data
    )
