-- Create users table for storing user information
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    password VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- User Preference Scores (사용자 선호도 점수)
    food FLOAT DEFAULT NULL COMMENT '음식 선호도 가중치',
    service FLOAT DEFAULT NULL COMMENT '서비스 선호도 가중치',
    ambience FLOAT DEFAULT NULL COMMENT '분위기 선호도 가중치',
    price FLOAT DEFAULT NULL COMMENT '가격 선호도 가중치',
    hygiene FLOAT DEFAULT NULL COMMENT '위생 선호도 가중치',
    waiting FLOAT DEFAULT NULL COMMENT '대기시간 선호도 가중치',
    accessibility FLOAT DEFAULT NULL COMMENT '접근성 선호도 가중치',
    
    -- 인덱스 추가 (검색 성능 향상)
    INDEX idx_email (email),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;