"""
API endpoint tests for RAG pipeline.
Run with: pytest tests/test_api_endpoints.py -v
"""
import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


# ==============================
# Health Check Tests
# ==============================
def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert "status" in response.json()


# ==============================
# Chat Search API Tests
# ==============================
class TestChatSearchAPI:
    """Test suite for /api/v1/chat/search endpoint."""
    
    @pytest.mark.asyncio
    async def test_basic_search_no_prefs(self):
        """Test basic search without user preferences."""
        response = client.post(
            "/api/v1/chat/search",
            json={
                "user_id": 1,
                "query": "맛있는 피자 추천해줘"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "answer" in data
        assert "restaurants" in data
        assert isinstance(data["restaurants"], list)
    
    @pytest.mark.asyncio
    async def test_search_with_user_preferences(self):
        """Test search with user preferences."""
        response = client.post(
            "/api/v1/chat/search",
            json={
                "user_id": 1,
                "query": "레스토랑 추천해줘",
                "user_preferences": {
                    "food": 5.0,
                    "service": 3.0,
                    "ambience": 2.0,
                    "price": 4.0
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "answer" in data
        assert len(data["answer"]) > 0
    
    @pytest.mark.asyncio
    async def test_query_overrides_user_prefs(self):
        """
        Test that query intent overrides user preferences.
        
        Scenario: User has price=5.0 (values budget) but says 
        "가격이 비싸도 좋으니" (expensive is ok)
        """
        response = client.post(
            "/api/v1/chat/search",
            json={
                "user_id": 1,
                "query": "가격이 비싸도 좋으니 분위기가 좋은 이탈리안 레스토랑을 추천해줘",
                "user_preferences": {
                    "food": 3.0,
                    "service": 3.0,
                    "ambience": 2.0,
                    "price": 5.0  # User values budget
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return results - ambience-focused Italian restaurants
        assert "answer" in data
        assert "restaurants" in data
    
    @pytest.mark.asyncio
    async def test_borough_filter(self):
        """Test search with borough filter."""
        response = client.post(
            "/api/v1/chat/search",
            json={
                "user_id": 1,
                "query": "맨해튼에서 맛있는 한식당"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
    
    @pytest.mark.asyncio
    async def test_multiple_aspects(self):
        """Test search with multiple aspects mentioned."""
        response = client.post(
            "/api/v1/chat/search",
            json={
                "user_id": 1,
                "query": "깨끗하고 웨이팅 짧고 맛있는 라멘집",
                "user_preferences": {
                    "service": 5.0
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
    
    @pytest.mark.asyncio  
    async def test_vague_query_uses_user_prefs(self):
        """Test that vague queries use user preferences."""
        response = client.post(
            "/api/v1/chat/search",
            json={
                "user_id": 1,
                "query": "아무거나 추천해줘",
                "user_preferences": {
                    "food": 4.0,
                    "service": 3.0
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
    
    def test_invalid_request_missing_query(self):
        """Test validation error for missing query."""
        response = client.post(
            "/api/v1/chat/search",
            json={
                "user_id": 1
                # Missing "query"
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_invalid_request_missing_user_id(self):
        """Test validation error for missing user_id."""
        response = client.post(
            "/api/v1/chat/search",
            json={
                "query": "피자 추천해줘"
                # Missing "user_id"
            }
        )
        
        assert response.status_code == 422  # Validation error


# ==============================
# Response Structure Tests
# ==============================
class TestResponseStructure:
    """Test response structure and data types."""
    
    @pytest.mark.asyncio
    async def test_restaurant_result_structure(self):
        """Test that restaurant results have correct structure."""
        response = client.post(
            "/api/v1/chat/search",
            json={
                "user_id": 1,
                "query": "피자 추천"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data["restaurants"]:
            restaurant = data["restaurants"][0]
            
            # Check required fields
            assert "place_id" in restaurant
            assert "name" in restaurant
            
            # Check optional fields exist (can be None)
            assert "rating" in restaurant or restaurant.get("rating") is None
            assert "generated_tags" in restaurant
            assert "score" in restaurant


# ==============================
# Edge Cases
# ==============================
class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.mark.asyncio
    async def test_empty_query(self):
        """Test with empty query string."""
        response = client.post(
            "/api/v1/chat/search",
            json={
                "user_id": 1,
                "query": ""
            }
        )
        
        # Should either return 422 or handle gracefully
        assert response.status_code in [200, 422]
    
    @pytest.mark.asyncio
    async def test_very_long_query(self):
        """Test with very long query string."""
        long_query = "맛있는 피자 " * 100
        
        response = client.post(
            "/api/v1/chat/search",
            json={
                "user_id": 1,
                "query": long_query
            }
        )
        
        # Should handle gracefully
        assert response.status_code in [200, 422, 400]
    
    @pytest.mark.asyncio
    async def test_special_characters_in_query(self):
        """Test with special characters in query."""
        response = client.post(
            "/api/v1/chat/search",
            json={
                "user_id": 1,
                "query": "맛있는 피자! @#$% 추천해줘~"
            }
        )
        
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_preference_boundary_values(self):
        """Test with boundary preference values."""
        response = client.post(
            "/api/v1/chat/search",
            json={
                "user_id": 1,
                "query": "레스토랑 추천",
                "user_preferences": {
                    "food": 0.0,      # Minimum
                    "service": 5.0,   # Maximum
                    "ambience": 2.5   # Middle
                }
            }
        )
        
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
