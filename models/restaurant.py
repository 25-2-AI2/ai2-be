"""
SQLAlchemy model for Restaurant table.
"""
from sqlalchemy import Column, String, Float, Integer

from core.database import Base


class Restaurant(Base):
    """Restaurant model representing the restaurants table."""
    
    __tablename__ = "restaurants"
    
    place_id = Column(String(255), primary_key=True, nullable=False, comment="Google Place ID")
    name = Column(String(255), nullable=False, comment="레스토랑 이름")
    grid = Column(String(50), nullable=True, comment="그리드 코드 (예: BK1, MN2)")
    address = Column(String(500), nullable=False, comment="주소")
    rating = Column(Float, nullable=True, comment="평균 평점 (0.0 ~ 5.0)")
    user_ratings_total = Column(Integer, nullable=True, comment="총 리뷰 수")
    phone_number = Column(String(50), nullable=True, comment="전화번호")
    primaryType = Column(String(255), nullable=True, comment="레스토랑 주요 타입")
    district = Column(String(100), nullable=False, comment="자치구")
    
    # Sentiment Average Scores
    S_food_avg = Column(Float, nullable=True, comment="음식 품질 평균 점수")
    S_service_avg = Column(Float, nullable=True, comment="서비스 품질 평균 점수")
    S_ambience_avg = Column(Float, nullable=True, comment="분위기 평균 점수")
    S_price_avg = Column(Float, nullable=True, comment="가격 만족도 평균 점수")
    S_hygiene_avg = Column(Float, nullable=True, comment="위생 상태 평균 점수")
    S_waiting_avg = Column(Float, nullable=True, comment="대기 시간 평균 점수")
    S_accessibility_avg = Column(Float, nullable=True, comment="접근성 평균 점수")
    
    def get_sentiment_scores(self) -> dict:
        """Return sentiment scores as a dictionary."""
        return {
            "food": self.S_food_avg,
            "service": self.S_service_avg,
            "ambience": self.S_ambience_avg,
            "price": self.S_price_avg,
            "hygiene": self.S_hygiene_avg,
            "waiting": self.S_waiting_avg,
            "accessibility": self.S_accessibility_avg
        }
    
    def get_top_attributes(self, min_threshold: float = 0.5, top_n: int = 2) -> list[str]:
        """
        Get top N attributes with scores above min_threshold.
        
        Args:
            min_threshold: Minimum score threshold to consider
            top_n: Maximum number of top attributes to return
            
        Returns:
            List of attribute names sorted by score descending
        """
        scores = self.get_sentiment_scores()
        # Filter out None values and scores below threshold
        valid_scores = {k: v for k, v in scores.items() if v is not None and v >= min_threshold}
        # Sort by score descending and get top N
        sorted_attrs = sorted(valid_scores.keys(), key=lambda x: valid_scores[x], reverse=True)
        return sorted_attrs[:top_n]
