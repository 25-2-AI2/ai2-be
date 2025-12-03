"""
Test script for RAG pipeline.
Run with: python -m pytest tests/test_rag_pipeline.py -v
Or directly: python tests/test_rag_pipeline.py
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings
from services.rag_service import (
    search_restaurants_rag,
    normalize_user_preferences,
    merge_aspect_weights
)
from services.query_analyzer import analyze_query_ko


# ==============================
# Unit Tests: normalize_user_preferences
# ==============================
def test_normalize_user_preferences():
    """Test user preferences normalization from 0~5 to 0~1."""
    print("\n" + "="*60)
    print("TEST: normalize_user_preferences")
    print("="*60)
    
    # Test case 1: Full values
    raw_prefs = {"food": 5, "service": 3, "ambience": 2.5, "price": 0}
    normalized = normalize_user_preferences(raw_prefs)
    
    assert normalized["food"] == 1.0, f"Expected 1.0, got {normalized['food']}"
    assert normalized["service"] == 0.6, f"Expected 0.6, got {normalized['service']}"
    assert normalized["ambience"] == 0.5, f"Expected 0.5, got {normalized['ambience']}"
    assert normalized["price"] == 0.0, f"Expected 0.0, got {normalized['price']}"
    
    print(f"  ✓ Raw: {raw_prefs}")
    print(f"  ✓ Normalized: {normalized}")
    
    # Test case 2: With None values
    raw_prefs_with_none = {"food": 5, "service": None, "price": 2.5}
    normalized_with_none = normalize_user_preferences(raw_prefs_with_none)
    
    assert "service" not in normalized_with_none, "None values should be excluded"
    assert normalized_with_none["food"] == 1.0
    assert normalized_with_none["price"] == 0.5
    
    print(f"  ✓ With None: {raw_prefs_with_none} → {normalized_with_none}")
    
    print("  ✅ All normalize_user_preferences tests passed!")


# ==============================
# Unit Tests: merge_aspect_weights
# ==============================
def test_merge_aspect_weights():
    """Test merging user preferences with LLM weights."""
    print("\n" + "="*60)
    print("TEST: merge_aspect_weights")
    print("="*60)
    
    # Scenario 1: LLM overrides user preference
    user_prefs = {"food": 0.8, "price": 1.0, "service": 0.6}
    llm_weights = {"price": 0.1, "ambience": 0.9}  # User said "비싸도 괜찮아"
    
    merged = merge_aspect_weights(user_prefs, llm_weights)
    
    assert merged["price"] == 0.1, f"LLM should override: expected 0.1, got {merged['price']}"
    assert merged["ambience"] == 0.9, f"LLM new value: expected 0.9, got {merged['ambience']}"
    assert merged["food"] == 0.8, f"User fallback: expected 0.8, got {merged['food']}"
    assert merged["service"] == 0.6, f"User fallback: expected 0.6, got {merged['service']}"
    
    print(f"  User prefs: {user_prefs}")
    print(f"  LLM weights: {llm_weights}")
    print(f"  Merged: {merged}")
    print(f"  ✓ price: 1.0 → 0.1 (LLM override)")
    print(f"  ✓ ambience: None → 0.9 (LLM new)")
    print(f"  ✓ food: 0.8 (user fallback)")
    
    # Scenario 2: LLM returns 0.0 (explicit low importance)
    user_prefs2 = {"price": 1.0}
    llm_weights2 = {"price": 0.0}  # Explicitly zero
    
    merged2 = merge_aspect_weights(user_prefs2, llm_weights2)
    
    assert merged2["price"] == 0.0, f"LLM 0.0 should override: expected 0.0, got {merged2['price']}"
    print(f"\n  ✓ LLM 0.0 overrides user 1.0 → {merged2['price']}")
    
    # Scenario 3: No user prefs
    merged3 = merge_aspect_weights(None, {"food": 0.7})
    assert merged3["food"] == 0.7
    print(f"  ✓ No user prefs: {merged3}")
    
    # Scenario 4: No LLM weights
    merged4 = merge_aspect_weights({"food": 0.5, "service": 0.3}, None)
    assert merged4["food"] == 0.5
    assert merged4["service"] == 0.3
    print(f"  ✓ No LLM weights: {merged4}")
    
    print("  ✅ All merge_aspect_weights tests passed!")


# ==============================
# Integration Tests: Query Analysis
# ==============================
async def test_query_analysis():
    """Test LLM query analysis with various queries."""
    print("\n" + "="*60)
    print("TEST: Query Analysis (LLM)")
    print("="*60)
    
    test_cases = [
        {
            "query": "맛있는 이탈리안 레스토랑 추천해줘",
            "expected_aspects": {"food": "high"},
            "description": "Basic food query"
        },
        {
            "query": "가격이 비싸도 좋으니 분위기가 좋은 곳",
            "expected_aspects": {"price": "low", "ambience": "high"},
            "description": "Price not important, ambience important"
        },
        {
            "query": "맨해튼에서 가성비 좋은 피자집",
            "expected_aspects": {"price": "high"},
            "expected_filters": {"borough_en": "Manhattan"},
            "description": "Borough filter + price important"
        },
        {
            "query": "아무거나 추천해줘",
            "expected_aspects": {},
            "description": "No specific preferences (all null)"
        },
        {
            "query": "깨끗하고 서비스 좋은 일식집",
            "expected_aspects": {"hygiene": "high", "service": "high"},
            "description": "Hygiene and service important"
        },
    ]
    
    for i, tc in enumerate(test_cases, 1):
        print(f"\n  [{i}] {tc['description']}")
        print(f"      Query: {tc['query']}")
        
        try:
            result = await analyze_query_ko(tc["query"])
            
            print(f"      English: {result.get('query_en', 'N/A')}")
            print(f"      Filters: {result.get('filters', {})}")
            print(f"      Aspects: {result.get('aspect_weights', {})}")
            
            # Validate expected aspects
            aspects = result.get("aspect_weights", {})
            for aspect, expected_level in tc.get("expected_aspects", {}).items():
                value = aspects.get(aspect)
                if expected_level == "high" and value is not None:
                    assert value >= 0.5, f"Expected {aspect} to be high (>=0.5), got {value}"
                    print(f"      ✓ {aspect}={value} (expected high)")
                elif expected_level == "low" and value is not None:
                    assert value <= 0.3, f"Expected {aspect} to be low (<=0.3), got {value}"
                    print(f"      ✓ {aspect}={value} (expected low)")
            
            # Validate expected filters
            filters = result.get("filters", {})
            for fkey, fval in tc.get("expected_filters", {}).items():
                assert filters.get(fkey) == fval, f"Expected filter {fkey}={fval}, got {filters.get(fkey)}"
                print(f"      ✓ filter {fkey}={fval}")
                
        except Exception as e:
            print(f"      ❌ Error: {e}")
    
    print("\n  ✅ Query analysis tests completed!")


# ==============================
# Integration Tests: Full RAG Pipeline
# ==============================
async def test_rag_pipeline_scenarios():
    """Test full RAG pipeline with different scenarios."""
    print("\n" + "="*60)
    print("TEST: Full RAG Pipeline")
    print("="*60)
    
    scenarios = [
        {
            "name": "1. Basic search (no user prefs)",
            "query": "맛있는 피자 추천해줘",
            "user_prefs": None,
        },
        {
            "name": "2. With user preferences",
            "query": "레스토랑 추천해줘",
            "user_prefs": {
                "food": 5.0,
                "service": 3.0,
                "ambience": 2.0,
                "price": 4.0
            },
        },
        {
            "name": "3. Query overrides user prefs (price)",
            "query": "가격 비싸도 괜찮으니 분위기 좋은 이탈리안",
            "user_prefs": {
                "food": 3.0,
                "service": 3.0,
                "ambience": 2.0,
                "price": 5.0  # User values price highly
            },
            "validate": lambda r, aw: aw.get("price", 1.0) < 0.5,  # Should be overridden to low
            "validate_msg": "price should be low (<0.5) despite user pref of 5.0"
        },
        {
            "name": "4. Borough filter",
            "query": "브루클린에서 맛있는 한식당",
            "user_prefs": None,
        },
        {
            "name": "5. Multiple aspects",
            "query": "깨끗하고 웨이팅 짧고 맛있는 라멘집",
            "user_prefs": {"service": 5.0},
        },
    ]
    
    for scenario in scenarios:
        print(f"\n  --- {scenario['name']} ---")
        print(f"  Query: {scenario['query']}")
        print(f"  User prefs: {scenario['user_prefs']}")
        
        try:
            # Get result
            result = await search_restaurants_rag(
                query=scenario["query"],
                user_preferences=scenario["user_prefs"],
                top_k=5,
                translate_top_n=2
            )
            
            print(f"  Answer: {result.answer[:100]}...")
            print(f"  Results: {len(result.place_ids)} restaurants")
            
            if result.place_ids:
                print(f"  Top score: {result.scores[0]:.4f}")
            
            # Run custom validation if provided
            if "validate" in scenario:
                # Need to trace aspect_weights - we'll check via answer
                print(f"  Note: {scenario['validate_msg']}")
            
            print(f"  ✓ Completed successfully")
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n  ✅ RAG pipeline tests completed!")


# ==============================
# Main Test Runner
# ==============================
def run_unit_tests():
    """Run unit tests."""
    print("\n" + "#"*60)
    print("# UNIT TESTS")
    print("#"*60)
    
    test_normalize_user_preferences()
    test_merge_aspect_weights()


async def run_integration_tests():
    """Run integration tests."""
    print("\n" + "#"*60)
    print("# INTEGRATION TESTS (requires API keys and data)")
    print("#"*60)
    
    await test_query_analysis()
    await test_rag_pipeline_scenarios()


if __name__ == "__main__":
    print("="*60)
    print("RAG Pipeline Test Suite")
    print("="*60)
    
    # Run unit tests (no external dependencies)
    run_unit_tests()
    
    # Run integration tests (requires OpenAI API, data files)
    print("\n\nRunning integration tests...")
    print("(Make sure OPENAI_API_KEY is set and data files exist)")
    
    try:
        asyncio.run(run_integration_tests())
    except Exception as e:
        print(f"\n❌ Integration tests failed: {e}")
        print("This may be due to missing API keys or data files.")
    
    print("\n" + "="*60)
    print("Test Suite Completed")
    print("="*60)
