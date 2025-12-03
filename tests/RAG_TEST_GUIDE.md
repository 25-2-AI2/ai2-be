# RAG Pipeline 테스트 가이드

## 목차
1. [서버 실행](#1-서버-실행)
2. [Postman 테스트](#2-postman-테스트)
3. [curl 테스트](#3-curl-테스트)
4. [테스트 시나리오](#4-테스트-시나리오)
5. [Python 테스트 스크립트](#5-python-테스트-스크립트)

---

## 1. 서버 실행

```bash
cd E:\gitrepo\ai2-be

# 가상환경 활성화
.venv\Scripts\activate

# 환경변수 설정 (Windows)
set OPENAI_API_KEY=your-api-key-here

# 서버 실행
python main.py
# 또는
uvicorn main:app --reload --port 8000
```

서버가 실행되면: http://localhost:8000/docs 에서 Swagger UI 확인 가능

---

## 2. Postman 테스트

### 기본 설정
- **Method**: POST
- **URL**: `http://localhost:8000/api/v1/chat/search`
- **Headers**: 
  - `Content-Type: application/json`

### 테스트 케이스들

#### 2.1 기본 검색 (user_preferences 없음)
```json
{
    "user_id": 1,
    "query": "맛있는 피자 추천해줘"
}
```

#### 2.2 User Preferences 포함
```json
{
    "user_id": 1,
    "query": "레스토랑 추천해줘",
    "user_preferences": {
        "food": 5.0,
        "service": 3.0,
        "ambience": 2.0,
        "price": 4.0,
        "hygiene": 3.0,
        "waiting": 2.0,
        "accessibility": 1.0
    }
}
```

#### 2.3 ⭐ 쿼리가 User Preference 오버라이드 (핵심 테스트)
**시나리오**: 유저가 가성비(price=5.0)를 중시하지만, 쿼리에서 "비싸도 괜찮다"고 함

```json
{
    "user_id": 1,
    "query": "가격이 비싸도 좋으니 분위기가 좋은 이탈리안 레스토랑을 추천해줘",
    "user_preferences": {
        "food": 3.0,
        "service": 3.0,
        "ambience": 2.0,
        "price": 5.0
    }
}
```

**기대 결과**:
- price 가중치가 낮아짐 (0.1~0.2, 원래 5.0/5=1.0에서 오버라이드)
- ambience 가중치가 높아짐 (0.8~0.9)
- 분위기 좋은 이탈리안 레스토랑 우선 추천

#### 2.4 지역 필터 테스트
```json
{
    "user_id": 1,
    "query": "맨해튼에서 가성비 좋은 한식당 추천해줘"
}
```

#### 2.5 여러 aspect 동시 언급
```json
{
    "user_id": 1,
    "query": "깨끗하고 웨이팅 짧고 맛있는 라멘집 찾아줘",
    "user_preferences": {
        "service": 5.0
    }
}
```

**기대 결과**:
- hygiene: 높음 (쿼리에서 "깨끗하고")
- waiting: 높음 (쿼리에서 "웨이팅 짧고")  
- food: 높음 (쿼리에서 "맛있는")
- service: 1.0 (user_preference에서, 쿼리에 없음)

#### 2.6 아무것도 특정하지 않는 쿼리
```json
{
    "user_id": 1,
    "query": "아무거나 추천해줘",
    "user_preferences": {
        "food": 4.0,
        "service": 3.0
    }
}
```

**기대 결과**:
- LLM이 모든 aspect를 null로 반환
- user_preferences가 그대로 사용됨

---

## 3. curl 테스트

### Windows CMD
```cmd
curl -X POST "http://localhost:8000/api/v1/chat/search" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\": 1, \"query\": \"맛있는 피자 추천해줘\"}"
```

### Windows PowerShell
```powershell
$body = @{
    user_id = 1
    query = "가격이 비싸도 좋으니 분위기가 좋은 이탈리안"
    user_preferences = @{
        food = 3.0
        service = 3.0
        ambience = 2.0
        price = 5.0
    }
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/v1/chat/search" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body
```

### Linux/Mac
```bash
curl -X POST "http://localhost:8000/api/v1/chat/search" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "query": "가격이 비싸도 좋으니 분위기가 좋은 이탈리안",
    "user_preferences": {
        "food": 3.0,
        "service": 3.0,
        "ambience": 2.0,
        "price": 5.0
    }
}'
```

---

## 4. 테스트 시나리오

### 시나리오 A: 값 범위 정규화 검증

| DB 값 (0~5) | 정규화 후 (0~1) |
|-------------|-----------------|
| 0 | 0.0 |
| 2.5 | 0.5 |
| 5 | 1.0 |

### 시나리오 B: 쿼리 우선순위 검증

| User Pref | Query 의도 | LLM 분석 | 최종 값 |
|-----------|-----------|----------|---------|
| price=5.0 | "비싸도 괜찮아" | price=0.1 | **0.1** (쿼리 우선) |
| price=5.0 | (언급 안함) | price=null | **1.0** (user pref) |
| ambience=2.0 | "분위기 좋은" | ambience=0.9 | **0.9** (쿼리 우선) |
| food=null | "맛있는" | food=0.8 | **0.8** (쿼리) |

### 시나리오 C: 다양한 쿼리 패턴

| 쿼리 | 예상 LLM 분석 |
|------|--------------|
| "맛있는 피자" | food=0.8, desired_types=["pizza_restaurant"] |
| "조용한 분위기 데이트" | ambience=0.9 |
| "가성비 좋은" | price=0.8 |
| "비싸도 좋으니" | price=0.1~0.2 |
| "깨끗한" | hygiene=0.8 |
| "웨이팅 짧은" | waiting=0.8 |
| "역 가까운" | accessibility=0.8 |
| "서비스 좋은" | service=0.8 |
| "아무거나" | 모든 aspect=null |

---

## 5. Python 테스트 스크립트

### 테스트 실행
```bash
cd E:\gitrepo\ai2-be

# 단위 테스트만
python tests/test_rag_pipeline.py

# 또는 pytest 사용
pip install pytest pytest-asyncio
pytest tests/test_rag_pipeline.py -v
```

### 개별 컴포넌트 테스트
```python
import asyncio
from services.query_analyzer import analyze_query_ko
from services.rag_service import normalize_user_preferences, merge_aspect_weights

# 1. 쿼리 분석 테스트
async def test_query():
    result = await analyze_query_ko("가격 비싸도 분위기 좋은 곳")
    print(f"English: {result['query_en']}")
    print(f"Aspects: {result['aspect_weights']}")
    # price는 낮아야 하고 (0.1~0.2), ambience는 높아야 함 (0.8~0.9)

asyncio.run(test_query())

# 2. 정규화 테스트
raw = {"food": 5, "price": 2.5}
normalized = normalize_user_preferences(raw)
print(normalized)  # {'food': 1.0, 'price': 0.5}

# 3. 병합 테스트
user = {"food": 0.8, "price": 1.0}
llm = {"price": 0.1, "ambience": 0.9}
merged = merge_aspect_weights(user, llm)
print(merged)  # {'food': 0.8, 'price': 0.1, 'ambience': 0.9, ...}
```

---

## 6. 예상 응답 형식

```json
{
    "answer": "분위기 좋은 이탈리안 레스토랑을 추천해 드릴게요! ...",
    "restaurants": [
        {
            "place_id": "ChIJ...",
            "name": "Carbone",
            "rating": 4.6,
            "generated_tags": ["분위기 좋음", "데이트 추천"],
            "score": 3.245,
            "korean_pattern": "한국인들이 특히 파스타와 분위기를 좋아했어요..."
        },
        ...
    ]
}
```

---

## 7. 디버깅 팁

### 로그 확인
서버 콘솔에서 다음 로그를 확인:
- `[SearchEngine] Loading...` - 모델 로딩
- Cross-encoder 점수 계산 시간

### 일반적인 오류

| 오류 | 원인 | 해결 |
|------|------|------|
| `OPENAI_API_KEY not set` | 환경변수 미설정 | `set OPENAI_API_KEY=sk-...` |
| `File not found: df_dedup_enriched.parquet` | 데이터 파일 없음 | data 폴더에 파일 복사 |
| `No module named 'sentence_transformers'` | 패키지 미설치 | `pip install sentence-transformers` |
| Empty results | 필터가 너무 제한적 | borough 필터 제거하고 테스트 |
