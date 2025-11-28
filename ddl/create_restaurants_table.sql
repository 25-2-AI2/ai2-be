CREATE TABLE IF NOT EXISTS restaurants (
    place_id VARCHAR(255) PRIMARY KEY NOT NULL COMMENT 'Google Place ID (고유 식별자)',
    name VARCHAR(255) NOT NULL COMMENT '레스토랑 이름',
    grid VARCHAR(50) DEFAULT NULL COMMENT '그리드 코드 (예: BK1, MN2)',
    address VARCHAR(500) NOT NULL COMMENT '주소',
    rating FLOAT DEFAULT NULL COMMENT '평균 평점 (0.0 ~ 5.0)',
    user_ratings_total INT DEFAULT NULL COMMENT '총 리뷰 수',
    phone_number VARCHAR(50) DEFAULT NULL COMMENT '전화번호',
    primaryType VARCHAR(255) DEFAULT NULL COMMENT '레스토랑 주요 타입',
    district VARCHAR(100) NOT NULL COMMENT '자치구 (Brooklyn, Manhattan 등)',
    
    -- Sentiment Average Scores
    S_food_avg FLOAT DEFAULT NULL COMMENT '음식 품질 평균 점수',
    S_service_avg FLOAT DEFAULT NULL COMMENT '서비스 품질 평균 점수',
    S_ambience_avg FLOAT DEFAULT NULL COMMENT '분위기 평균 점수',
    S_price_avg FLOAT DEFAULT NULL COMMENT '가격 만족도 평균 점수',
    S_hygiene_avg FLOAT DEFAULT NULL COMMENT '위생 상태 평균 점수',
    S_waiting_avg FLOAT DEFAULT NULL COMMENT '대기 시간 평균 점수',
    S_accessibility_avg FLOAT DEFAULT NULL COMMENT '접근성 평균 점수',
    
    -- 인덱스
    INDEX idx_rating (rating),
    INDEX idx_district (district),
    INDEX idx_grid (grid),
    INDEX idx_food_score (S_food_avg),
    INDEX idx_service_score (S_service_avg),
    INDEX idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='레스토랑 기본 정보 및 감정 분석 점수';
