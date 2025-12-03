"""
RAG (Retrieval-Augmented Generation) service.
Integrates search_engine and query_analyzer for restaurant recommendations.
Uses Cross-Encoder based reranking and pattern translation.
"""
import asyncio
from typing import Dict, List, Optional

import pandas as pd
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import settings
from services.search_engine import get_search_engine
from services.query_analyzer import (
    analyze_query_ko, 
    get_preferred_pattern, 
    translate_pattern_to_ko
)


# Initialize OpenAI client using config
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


class RAGSearchResult:
    """Data class for RAG search results."""
    def __init__(self, answer: str, place_ids: List[str], 
                 scores: Optional[List[float]] = None,
                 korean_patterns: Optional[Dict[str, str]] = None,
                 pattern_sources: Optional[Dict[str, str]] = None):
        self.answer = answer
        self.place_ids = place_ids
        self.scores = scores or []
        self.korean_patterns = korean_patterns or {}
        self.pattern_sources = pattern_sources or {}


ANSWER_GENERATION_PROMPT = """
You are a friendly restaurant recommendation assistant for New York City.

Given a user's search query and a list of recommended restaurants, generate a natural, conversational response that:
1. Acknowledges the user's request
2. Briefly mentions why these restaurants are good matches
3. Highlights 1-2 standout features across the recommendations
4. Maintains a warm, helpful tone

Keep the response concise (2-3 sentences) and natural.

User Query: {query}
Recommended Restaurants: {restaurant_names}
User Preferences: {preferences}

Generate a natural response in Korean:
"""


def normalize_user_preferences(user_preferences: Dict[str, float]) -> Dict[str, float]:
    """
    Normalize user preferences from DB scale (0~5) to internal scale (0.0~1.0).
    
    Args:
        user_preferences: Dict with values in 0~5 range from DB
        
    Returns:
        Dict with values normalized to 0.0~1.0 range
    """
    if not user_preferences:
        return {}
    
    normalized = {}
    for key, value in user_preferences.items():
        if value is not None:
            # Normalize: 0~USER_PREF_MAX → 0.0~1.0
            normalized[key] = float(value) / settings.USER_PREF_MAX
    
    return normalized


def merge_aspect_weights(
    user_preferences: Optional[Dict[str, float]],
    llm_aspect_weights: Optional[Dict[str, float]]
) -> Dict[str, float]:
    """
    Merge user preferences and LLM-analyzed aspect weights.
    
    Priority Logic:
    - If LLM returns a value (including 0.0): Use LLM value (query takes priority)
    - If LLM returns null: Use user preference (if available)
    - If both are null/missing: Don't include in result
    
    This ensures that explicit user intent in the current query overrides stored preferences.
    
    Example:
    - User has price=5 (normalized to 1.0) stored in DB
    - User says "가격 비싸도 괜찮아" (expensive is ok)
    - LLM returns price=0.1 (low importance)
    - Result: price=0.1 (LLM value takes priority)
    
    Args:
        user_preferences: User's stored preferences (already normalized to 0.0~1.0)
        llm_aspect_weights: LLM-analyzed weights from current query (0.0~1.0, can be null)
        
    Returns:
        Merged aspect weights dictionary
    """
    aspect_weights = {}
    
    # All possible aspect keys
    all_aspects = ["food", "service", "ambience", "price", "hygiene", "waiting", "accessibility"]
    
    for aspect in all_aspects:
        llm_value = llm_aspect_weights.get(aspect) if llm_aspect_weights else None
        user_value = user_preferences.get(aspect) if user_preferences else None
        
        # Priority: LLM value (if not None) > User preference (if not None)
        if llm_value is not None:
            # LLM explicitly set a value (including 0.0) - use it
            aspect_weights[aspect] = float(llm_value)
        elif user_value is not None:
            # LLM didn't mention it, but user has a stored preference
            aspect_weights[aspect] = float(user_value)
        # else: Neither has a value, don't include
    
    return aspect_weights


@retry(wait=wait_exponential(min=1, max=8), stop=stop_after_attempt(3))
async def generate_answer(query_en: str, restaurant_names: List[str], 
                         user_preferences: Optional[Dict[str, float]] = None) -> str:
    """
    Generate natural language answer using LLM.
    
    Args:
        query_en: English query
        restaurant_names: List of recommended restaurant names
        user_preferences: User preference weights
        
    Returns:
        Natural language answer in Korean
    """
    # Format preferences for prompt
    if user_preferences:
        valid_prefs = {k: v for k, v in user_preferences.items() if v is not None and v > 0.1}
        if valid_prefs:
            top_prefs = sorted(valid_prefs.keys(), key=lambda x: valid_prefs[x], reverse=True)[:3]
            pref_str = ", ".join(top_prefs)
        else:
            pref_str = "general quality"
    else:
        pref_str = "general quality"
    
    # Format restaurant names
    if len(restaurant_names) > 5:
        rest_str = ", ".join(restaurant_names[:5]) + f" and {len(restaurant_names) - 5} more"
    else:
        rest_str = ", ".join(restaurant_names)
    
    prompt = ANSWER_GENERATION_PROMPT.format(
        query=query_en,
        restaurant_names=rest_str,
        preferences=pref_str
    )
    
    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        temperature=0.7,
        max_tokens=200,
        messages=[
            {"role": "system", "content": "You are a helpful restaurant recommendation assistant. Always respond in Korean."},
            {"role": "user", "content": prompt}
        ]
    )
    
    return response.choices[0].message.content.strip()


async def search_restaurants_rag(
    query: str,
    user_preferences: Optional[Dict[str, float]] = None,
    top_k: Optional[int] = None,
    translate_top_n: Optional[int] = None
) -> RAGSearchResult:
    """
    Search restaurants using hybrid search with Cross-Encoder reranking.
    
    This is the main entry point that integrates:
    1. Query analysis (Korean → English + filters + aspects)
    2. Hybrid search (BM25 + E5)
    3. Cross-Encoder based reranking
    4. Pattern extraction and translation
    5. Answer generation
    
    Priority Order:
    - Query-specific intent (from LLM analysis) takes highest priority
    - User's stored preferences are used only when LLM returns null for that aspect
    
    Example:
    - User has price=5 (high importance) saved in DB
    - User says "가격이 비싸도 좋으니 분위기가 좋은 이탈리안 레스토랑을 추천해줘"
    - LLM analyzes: price=0.1 (low), ambience=0.9 (high), food=null, service=null
    - Result: price=0.1 (LLM), ambience=0.9 (LLM), food=user_pref, service=user_pref
    
    Args:
        query: Korean natural language query
        user_preferences: Optional user preference weights from DB (0~5 scale)
        top_k: Number of results to return (default from config)
        translate_top_n: Number of top results to translate patterns for (default from config)
        
    Returns:
        RAGSearchResult with answer, place_ids, scores, korean_patterns, and pattern_sources
    """
    # Use config defaults if not specified
    if top_k is None:
        top_k = settings.SEARCH_TOP_N
    if translate_top_n is None:
        translate_top_n = settings.SEARCH_TRANSLATE_TOP_N
    
    # Step 1: Analyze query
    parsed = await analyze_query_ko(query)
    query_en = parsed.get("query_en", "").strip()
    filters = parsed.get("filters", {}) or {}
    llm_aspect_weights = parsed.get("aspect_weights", {}) or {}
    
    # Step 2: Normalize user preferences from DB scale (0~5) to internal scale (0.0~1.0)
    normalized_user_prefs = normalize_user_preferences(user_preferences) if user_preferences else {}
    
    # Step 3: Merge aspect weights (Query takes priority over user preferences)
    # - LLM value (including 0.0) overrides user preference
    # - null from LLM means "use user preference"
    aspect_weights = merge_aspect_weights(normalized_user_prefs, llm_aspect_weights)
    
    # If no weights at all, use balanced defaults
    if not aspect_weights:
        aspect_weights = {
            "food": 0.5,
            "service": 0.5,
            "ambience": 0.5,
            "price": 0.5
        }
    
    # Step 4: Get search engine and normalize types
    engine = get_search_engine()
    raw_desired = filters.get("desired_types")
    filters["desired_types"] = engine.normalize_desired_types(raw_desired)
    
    # Step 5: Perform re-ranking with Cross-Encoder
    result_df = engine.rerank(
        query=query_en,
        aspect_weights=aspect_weights,
        filters=filters,
        top_k_bm25=settings.SEARCH_TOP_K_BM25,
        top_k_e5=settings.SEARCH_TOP_K_E5,
        w_bm25=settings.SEARCH_W_BM25,
        w_e5=settings.SEARCH_W_E5,
        w_H=settings.SEARCH_W_H,
        w_T=settings.SEARCH_W_T,
        w_type=settings.SEARCH_W_TYPE,
        w_ce=settings.SEARCH_W_CE,
        top_n=top_k
    )
    
    # Step 6: Extract results
    if result_df.empty:
        return RAGSearchResult(
            answer="죄송합니다. 검색 조건에 맞는 레스토랑을 찾지 못했습니다. 다른 조건으로 다시 시도해주세요.",
            place_ids=[],
            scores=[],
            korean_patterns={},
            pattern_sources={}
        )
    
    # Use place_id if available, otherwise use restaurant_id
    id_col = "place_id" if "place_id" in result_df.columns else "restaurant_id"
    place_ids = result_df[id_col].astype(str).tolist()
    scores = result_df["Score_final"].tolist()
    restaurant_names = result_df["name"].tolist()
    
    # Step 7: Extract and process reviewer patterns
    result_df = result_df.copy()
    
    # Extract preferred patterns (Korean first, then Non-Korean)
    if "summary" in result_df.columns:
        pattern_data = result_df["summary"].apply(get_preferred_pattern).apply(pd.Series)
        pattern_data.columns = ["pattern_source", "pattern_en_body"]
        result_df = pd.concat([result_df, pattern_data], axis=1)
    else:
        result_df["pattern_source"] = ""
        result_df["pattern_en_body"] = ""
    
    # Step 8: Translate top N patterns to Korean
    df_top = result_df.head(translate_top_n)
    texts_to_translate = df_top["pattern_en_body"].fillna("").tolist()
    
    # Parallel translation
    translation_tasks = [translate_pattern_to_ko(text) for text in texts_to_translate]
    translated_list = await asyncio.gather(*translation_tasks)
    
    # Assign translated patterns
    df_top = df_top.copy()
    df_top["pattern_ko_body"] = translated_list
    
    result_df["pattern_ko_body"] = ""
    result_df.loc[df_top.index, "pattern_ko_body"] = df_top["pattern_ko_body"]
    
    # Build pattern dictionaries
    korean_patterns = {}
    pattern_sources = {}
    
    for _, row in result_df.iterrows():
        place_id = str(row[id_col])
        pattern_ko = row.get("pattern_ko_body", "")
        source = row.get("pattern_source", "")
        
        if pattern_ko:
            korean_patterns[place_id] = pattern_ko
        if source:
            pattern_sources[place_id] = source
    
    # Step 9: Generate answer
    answer = await generate_answer(query_en, restaurant_names, aspect_weights)
    
    return RAGSearchResult(
        answer=answer,
        place_ids=place_ids,
        scores=scores,
        korean_patterns=korean_patterns,
        pattern_sources=pattern_sources
    )
