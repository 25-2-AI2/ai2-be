"""
SQLAlchemy model for User table.
"""
from sqlalchemy import Column, Integer, String, Float, TIMESTAMP
from sqlalchemy.sql import func

from core.database import Base


class User(Base):
    """User model representing the users table."""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    password = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # User Preference Scores
    food = Column(Float, nullable=True, comment="음식 선호도 가중치")
    service = Column(Float, nullable=True, comment="서비스 선호도 가중치")
    ambience = Column(Float, nullable=True, comment="분위기 선호도 가중치")
    price = Column(Float, nullable=True, comment="가격 선호도 가중치")
    hygiene = Column(Float, nullable=True, comment="위생 선호도 가중치")
    waiting = Column(Float, nullable=True, comment="대기시간 선호도 가중치")
    accessibility = Column(Float, nullable=True, comment="접근성 선호도 가중치")
    
    def get_preferences(self) -> dict:
        """Return user preferences as a dictionary."""
        return {
            "food": self.food,
            "service": self.service,
            "ambience": self.ambience,
            "price": self.price,
            "hygiene": self.hygiene,
            "waiting": self.waiting,
            "accessibility": self.accessibility
        }
