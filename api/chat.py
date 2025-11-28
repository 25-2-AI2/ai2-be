"""
Chat API endpoints.
Handles RAG-based restaurant search.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from core.database import get_db
from models.restaurant import Restaurant
from schemas.chat import ChatSearchRequest, ChatSearchResponse
from schemas.restaurant import RestaurantSearchResult
from services.translate_service import translate_to_english, is_korean
from services.rag_service import search_restaurants_rag
from services.tag_service import generate_tags_from_restaurant

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/search", response_model=ChatSearchResponse)
async def chat_search(request: ChatSearchRequest, db: Session = Depends(get_db)):
    """
    Search restaurants using RAG pipeline.
    
    Process:
    1. Translate Korean query to English (if needed)
    2. Perform RAG search to get answer and place_ids
    3. Fetch restaurant details from database
    4. Generate tags for each restaurant
    """
    query = request.query
    
    # Step 1: Translate query if Korean
    if is_korean(query):
        translated_query = await translate_to_english(query)
    else:
        translated_query = query
    
    # Step 2: Get user preferences as dict
    user_prefs = None
    if request.user_preferences:
        user_prefs = request.user_preferences.model_dump()
    
    # Step 3: Perform RAG search
    rag_result = await search_restaurants_rag(translated_query, user_prefs)
    
    # Step 4: Fetch restaurants from database
    restaurants_data: List[RestaurantSearchResult] = []
    
    if rag_result.place_ids:
        restaurants = db.query(Restaurant).filter(
            Restaurant.place_id.in_(rag_result.place_ids)
        ).all()
        
        # Build response for each restaurant
        for restaurant in restaurants:
            generated_tags = generate_tags_from_restaurant(restaurant)
            restaurants_data.append(RestaurantSearchResult(
                place_id=restaurant.place_id,
                name=restaurant.name,
                rating=restaurant.rating,
                generated_tags=generated_tags
            ))
    
    return ChatSearchResponse(
        answer=rag_result.answer,
        restaurants=restaurants_data
    )
