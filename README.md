# Restaurant Recommendation API

FastAPI 기반의 레스토랑 추천 시스템 백엔드 API 서버입니다. RAG 챗봇 파이프라인과 Map 서비스 프론트엔드를 지원합니다.

## 프로젝트 구조

```
ai2-be/
├── core/               # 설정 및 데이터베이스 연결
│   ├── config.py       # 환경변수 로드 및 설정 관리
│   └── database.py     # SQLAlchemy 세션 관리
├── models/             # SQLAlchemy ORM 모델
│   ├── user.py         # 사용자 모델
│   └── restaurant.py   # 레스토랑 모델
├── schemas/            # Pydantic Request/Response DTO
│   ├── user.py         # 사용자 스키마
│   ├── restaurant.py   # 레스토랑 스키마
│   └── chat.py         # 챗봇 스키마
├── services/           # 비즈니스 로직
│   ├── tag_service.py          # 태그 생성 로직 (공통)
│   ├── translate_service.py    # 번역 서비스 (OpenAI)
│   ├── rag_service.py          # RAG 검색 (Mock)
│   └── recommend_service.py    # 추천 로직 (우선순위 큐)
├── api/                # API 엔드포인트
│   ├── users.py        # 사용자 관련 API
│   ├── restaurants.py  # 레스토랑 관련 API
│   └── chat.py         # 챗봇 관련 API
├── ddl/                # 데이터베이스 DDL 스크립트
│   ├── create_users_tables.sql
│   ├── create_restaurants_table.sql
│   └── insert_restaurants_data.sql
├── main.py             # FastAPI 앱 진입점
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## 설치 방법

### 1. 가상환경 생성 및 활성화

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. 환경변수 설정

`.env.example` 파일을 복사하여 `.env` 파일을 생성하고 필요한 값을 설정합니다:

```bash
cp .env.example .env
```

`.env` 파일을 편집하여 다음 항목을 설정하세요:
- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_DATABASE`: MySQL 데이터베이스 연결 정보
- `OPEN_API_KEY`: OpenAI API 키 (번역 기능에 사용)
- `TAG_THRESHOLD`: 태그 생성 임계값 (기본값: 0.5)
- `MIN_SCORE_THRESHOLD`: 추천 시 최소 점수 임계값 (기본값: 0.5)

### 4. 데이터베이스 설정

MySQL에서 데이터베이스와 테이블을 생성합니다:

```sql
CREATE DATABASE ai2 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ai2;

-- ddl/ 폴더의 SQL 파일들 실행
```

## 실행 방법

### 개발 모드 (자동 리로드)

```bash
uvicorn main:app --reload
```

### 프로덕션 모드

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API 문서

서버 실행 후 다음 URL에서 API 문서를 확인할 수 있습니다:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API 명세

### 1. GET /users/{user_id}

사용자 정보 조회

**Response:**
```json
{
  "id": 1,
  "email": "user@example.com",
  "tags": {
    "food": 1.2,
    "service": 0.5,
    "ambience": null,
    "price": 0.8,
    "hygiene": null,
    "waiting": null,
    "accessibility": null
  }
}
```

### 2. PATCH /users/{user_id}/preferences

사용자 선호도 부분 업데이트

**Request:**
```json
{
  "food": 1.5,
  "service": 0.8
}
```

**Response:** 200 OK (Empty Body)

### 3. POST /chat/search

RAG 기반 레스토랑 검색

**Request:**
```json
{
  "user_id": 1,
  "query": "브루클린 피자 맛집",
  "user_preferences": {
    "food": 1.2,
    "service": 0.5
  }
}
```

**Response:**
```json
{
  "answer": "Based on your search for 'Brooklyn pizza restaurants'...",
  "restaurants": [
    {
      "place_id": "ChIJ...",
      "name": "Pizza Place",
      "rating": 4.5,
      "generated_tags": ["맛 좋음", "분위기 좋음"]
    }
  ]
}
```

### 4. GET /restaurants/{place_id}

레스토랑 상세 정보 조회

**Response:**
```json
{
  "place_id": "ChIJ...",
  "name": "Restaurant Name",
  "grid": "BK1",
  "address": "123 Main St, Brooklyn, NY",
  "rating": 4.5,
  "user_ratings_total": 1000,
  "primaryType": "italian_restaurant",
  "district": "Brooklyn",
  "generated_tags": ["맛 좋음", "서비스 좋음"]
}
```

### 5. GET /restaurants/{place_id}/recommend

유사 레스토랑 추천

**Request:** Path Parameter로 `place_id` 전달

**Response:**
```json
[
  {
    "place_id": "ChIJ...",
    "name": "Similar Restaurant",
    "grid": "BK1",
    "address": "456 Oak Ave, Brooklyn, NY",
    "rating": 4.3,
    "user_ratings_total": 500,
    "primaryType": "italian_restaurant",
    "district": "Brooklyn",
    "generated_tags": ["맛 좋음"],
    "match_reason": "같은 지역(grid) + 같은 타입 + 유사한 강점"
  }
]
```

## 태그 생성 로직

`S_*_avg` 점수(범위: -2 ~ 2)가 `TAG_THRESHOLD`(기본값: 0.5)를 초과하면 해당 속성에 대한 한국어 태그가 생성됩니다:

| 속성 | 태그 |
|------|------|
| food | 맛 좋음 |
| service | 서비스 좋음 |
| ambience | 분위기 좋음 |
| price | 가성비 좋음 |
| hygiene | 청결함 |
| waiting | 대기 시간 짧음 |
| accessibility | 접근성 좋음 |

## 추천 로직

레스토랑 추천은 우선순위 큐 방식으로 동작합니다:

1. **1순위**: grid 일치 + primaryType 일치 + 상위 속성 점수 ≥ MIN_SCORE_THRESHOLD
2. **2순위**: district 일치 + primaryType 일치 + 상위 속성 점수 ≥ MIN_SCORE_THRESHOLD
3. **3순위**: grid 일치 + 상위 속성 점수 ≥ MIN_SCORE_THRESHOLD (타입 무관)
4. **4순위**: district 일치 + 상위 속성 점수 ≥ MIN_SCORE_THRESHOLD (타입 무관)

각 우선순위에서 검색하여 총 5개의 레스토랑을 채우면 검색을 종료합니다.

## TODO

- [ ] RAG 서비스 실제 구현 (현재 Mock)
  - BGE-M3 임베딩 모델 연동
  - FAISS 벡터 DB 연동
  - LLM 기반 답변 생성
- [ ] 인증/인가 시스템 구현
- [ ] 테스트 코드 작성
- [ ] 로깅 시스템 구현
- [ ] 에러 핸들링 강화
