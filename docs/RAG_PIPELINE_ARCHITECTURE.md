# RAG 파이프라인 구조 및 동작 원리

## 목차
1. [전체 아키텍처](#1-전체-아키텍처)
2. [컴포넌트별 상세 설명](#2-컴포넌트별-상세-설명)
3. [데이터 흐름](#3-데이터-흐름)
4. [우선순위 로직](#4-우선순위-로직)
5. [점수 계산 공식](#5-점수-계산-공식)
6. [파일 구조](#6-파일-구조)

---

## 1. 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           RAG Pipeline Architecture                          │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌──────────────┐
                              │   Client     │
                              │   Request    │
                              └──────┬───────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                            api/chat.py                                      │
│  POST /api/v1/chat/search                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Input: {user_id, query, user_preferences?}                          │   │
│  │                                                                      │   │
│  │ 1. Get User Preferences                                             │   │
│  │    - request.user_preferences (우선)                                │   │
│  │    - DB에서 user_id로 조회 (fallback)                               │   │
│  │                                                                      │   │
│  │ 2. Call RAG Service                                                 │   │
│  │                                                                      │   │
│  │ 3. Fetch Restaurants from DB                                        │   │
│  │                                                                      │   │
│  │ 4. Generate Tags (tag_service)                                      │   │
│  │                                                                      │   │
│  │ Output: {answer, restaurants[]}                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                        services/rag_service.py                             │
│  search_restaurants_rag()                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                      │   │
│  │ Step 1: Query Analysis (query_analyzer.py)                          │   │
│  │         Korean → English + filters + aspect_weights                 │   │
│  │                                                                      │   │
│  │ Step 2: Normalize User Preferences (0~5 → 0~1)                      │   │
│  │                                                                      │   │
│  │ Step 3: Merge Aspect Weights                                        │   │
│  │         LLM값 (not null) > User Preference > Default                │   │
│  │                                                                      │   │
│  │ Step 4: Search & Rerank (search_engine.py)                          │   │
│  │                                                                      │   │
│  │ Step 5: Extract Patterns                                            │   │
│  │                                                                      │   │
│  │ Step 6: Translate Patterns (Top N)                                  │   │
│  │                                                                      │   │
│  │ Step 7: Generate Answer (LLM)                                       │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                       services/search_engine.py                            │
│  SearchEngine.rerank()                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                      │   │
│  │ 1. Compute Hybrid Scores                                            │   │
│  │    S_hybrid = w_bm25 × BM25_norm + w_e5 × E5_norm                   │   │
│  │                                                                      │   │
│  │ 2. Build Candidate Pool                                             │   │
│  │    Top-K from BM25 ∪ Top-K from E5                                  │   │
│  │                                                                      │   │
│  │ 3. Apply Filters                                                    │   │
│  │    - borough_en (지역)                                              │   │
│  │    - min_rating (최소 평점)                                         │   │
│  │                                                                      │   │
│  │ 4. Compute Type Score                                               │   │
│  │    S_type = 1.0 if matches desired_types else 0.0                   │   │
│  │                                                                      │   │
│  │ 5. Compute Cross-Encoder Scores                                     │   │
│  │    Query + [PREF] user_preferences → Document                       │   │
│  │                                                                      │   │
│  │ 6. Final Score                                                      │   │
│  │    Score = w_H×S_hybrid + w_T×S_conf + w_type×S_type + w_ce×S_ce   │   │
│  │                                                                      │   │
│  │ 7. Sort & Return Top-N                                              │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 컴포넌트별 상세 설명

### 2.1 api/chat.py
**역할**: API 엔드포인트, 요청/응답 처리

```python
# 주요 로직
1. User Preferences 결정
   - request.user_preferences 있으면 사용
   - 없으면 DB에서 user_id로 조회

2. RAG 검색 호출
   - search_restaurants_rag(query, user_prefs, top_k=20)

3. DB에서 레스토랑 정보 조회
   - place_id로 Restaurant 테이블 조회

4. 태그 생성
   - generate_tags_from_restaurant()

5. 응답 구성
   - answer + restaurants[]
```

### 2.2 services/query_analyzer.py
**역할**: 한국어 쿼리 분석 (LLM 기반)

```python
# 입력
query_ko: "가격 비싸도 괜찮으니 분위기 좋은 이탈리안"

# 출력
{
    "query_en": "Italian restaurant with great ambience, price doesn't matter",
    "filters": {
        "borough_en": null,
        "desired_types": ["italian_restaurant"],
        "min_rating": null
    },
    "aspect_weights": {
        "food": null,        # 언급 안함 → user pref 사용
        "service": null,
        "ambience": 0.9,     # "분위기 좋은" → 높음
        "price": 0.1,        # "비싸도 괜찮으니" → 낮음 (중요하지 않음)
        "hygiene": null,
        "waiting": null,
        "accessibility": null
    }
}
```

### 2.3 services/rag_service.py
**역할**: RAG 파이프라인 메인 오케스트레이터

```python
# 핵심 함수들

normalize_user_preferences(user_prefs)
  # DB의 0~5 → 내부 0~1로 변환

merge_aspect_weights(user_prefs, llm_weights)
  # 우선순위: LLM값(null 아닌 경우) > User Preference

search_restaurants_rag(query, user_prefs, top_k, translate_top_n)
  # 전체 파이프라인 실행
```

### 2.4 services/search_engine.py
**역할**: 하이브리드 검색 + Cross-Encoder 리랭킹

```python
# 데이터 소스 (Lazy Loading)
- df_dedup_enriched.parquet  # 레스토랑 데이터
- emb_e5.npy                 # E5 임베딩
- bm25.pkl                   # BM25 인덱스

# 모델
- intfloat/e5-large-v2                    # 쿼리 인코더
- cross-encoder/ms-marco-MiniLM-L-6-v2    # Cross-Encoder
```

---

## 3. 데이터 흐름

### 3.1 User Preferences 흐름

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  DB (users)     │     │  Request Body   │     │  LLM Analysis   │
│  0~5 scale      │     │  0~5 scale      │     │  0~1 scale      │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │ fallback              │ priority              │ highest
         │                       │                       │
         └───────────┬───────────┘                       │
                     │                                   │
                     ▼                                   │
         ┌───────────────────────┐                       │
         │ normalize_user_prefs  │                       │
         │ (0~5 → 0~1)           │                       │
         └───────────┬───────────┘                       │
                     │                                   │
                     └───────────────┬───────────────────┘
                                     │
                                     ▼
                          ┌───────────────────────┐
                          │ merge_aspect_weights  │
                          │ LLM > User > Default  │
                          └───────────────────────┘
                                     │
                                     ▼
                          ┌───────────────────────┐
                          │ Final aspect_weights  │
                          │ (0~1 scale)           │
                          └───────────────────────┘
```

### 3.2 검색 점수 흐름

```
Query: "맛있는 피자"
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Candidate Generation                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐                    ┌─────────────┐         │
│  │    BM25     │                    │     E5      │         │
│  │  (Sparse)   │                    │   (Dense)   │         │
│  └──────┬──────┘                    └──────┬──────┘         │
│         │                                  │                 │
│         ▼                                  ▼                 │
│    Top-60 by                          Top-60 by             │
│    keyword match                      semantic sim          │
│         │                                  │                 │
│         └──────────────┬───────────────────┘                 │
│                        │                                     │
│                        ▼                                     │
│              Unique candidates                               │
│              (60~120 restaurants)                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Score Computation                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  S_hybrid = 0.1 × BM25_norm + 0.9 × E5_norm                 │
│                                                              │
│  S_type = 1.0 if "pizza_restaurant" in types else 0.0       │
│                                                              │
│  S_ce = CrossEncoder(query + [PREF], doc_text)              │
│                                                              │
│  Score_final = 1.0×S_hybrid + 0.3×S_conf + 0.5×S_type       │
│              + 2.0×S_ce                                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
                    Top-20 Results
```

---

## 4. 우선순위 로직

### 4.1 Aspect Weights 우선순위

| 우선순위 | 소스 | 조건 | 예시 |
|---------|------|------|------|
| 1 (최고) | LLM | 값이 null이 아님 (0.0 포함) | 쿼리: "비싸도 괜찮아" → price=0.1 |
| 2 | User Pref | LLM이 null 반환 | 쿼리에서 언급 안함 → DB값 사용 |
| 3 (최저) | Default | 둘 다 없음 | {food:0.5, service:0.5, ...} |

### 4.2 예시 시나리오

```
User DB: {food: 3.0, price: 5.0, service: 2.0}  (0~5 scale)
          ↓ normalize
         {food: 0.6, price: 1.0, service: 0.4}  (0~1 scale)

Query: "가격 비싸도 괜찮으니 분위기 좋은 곳"

LLM 분석: {price: 0.1, ambience: 0.9, others: null}

Merge 결과:
- price: 0.1      (LLM - 쿼리에서 "비싸도 괜찮다")
- ambience: 0.9   (LLM - 쿼리에서 "분위기 좋은")
- food: 0.6       (User - 쿼리에서 언급 안함)
- service: 0.4    (User - 쿼리에서 언급 안함)
```

---

## 5. 점수 계산 공식

### 5.1 Hybrid Score
```
S_hybrid = w_bm25 × normalize(BM25_scores) + w_e5 × normalize(E5_scores)

Default: w_bm25=0.1, w_e5=0.9
```

### 5.2 Cross-Encoder Score
```
query_for_ce = f"{query_en} [PREF] {user_pref_text}"

S_ce = normalize(CrossEncoder.predict(query_for_ce, doc_text))
```

### 5.3 Final Score
```
Score_final = w_H × S_hybrid 
            + w_T × S_conf 
            + w_type × S_type 
            + w_ce × S_ce

Default weights:
- w_H = 1.0     (Hybrid)
- w_T = 0.3     (Confidence)
- w_type = 0.5  (Type matching)
- w_ce = 2.0    (Cross-Encoder) ← 가장 큰 영향
```

---

## 6. 파일 구조

```
E:\gitrepo\ai2-be\
├── api/
│   ├── chat.py              # POST /chat/search
│   ├── users.py             # GET/PATCH /users
│   └── restaurants.py       # Restaurant endpoints
│
├── services/
│   ├── rag_service.py       # RAG orchestrator
│   ├── search_engine.py     # Hybrid search + CrossEncoder
│   ├── query_analyzer.py    # LLM query analysis
│   ├── tag_service.py       # Tag generation
│   └── translate_service.py # Translation utils
│
├── schemas/
│   ├── chat.py              # ChatSearchRequest/Response
│   ├── user.py              # UserPreferences
│   └── restaurant.py        # RestaurantSearchResult
│
├── models/
│   ├── user.py              # User SQLAlchemy model
│   └── restaurant.py        # Restaurant SQLAlchemy model
│
├── data/                    # 검색 데이터 (lazy loaded)
│   ├── df_dedup_enriched.parquet
│   ├── emb_e5.npy
│   └── bm25.pkl
│
└── tests/
    ├── test_rag_pipeline.py
    ├── test_api_endpoints.py
    └── RAG_TEST_GUIDE.md
```

---

## 7. 주요 설정값

| 설정 | 값 | 설명 |
|------|-----|------|
| `top_k_bm25` | 60 | BM25 후보 수 |
| `top_k_e5` | 60 | E5 후보 수 |
| `w_bm25` | 0.1 | BM25 가중치 |
| `w_e5` | 0.9 | E5 가중치 |
| `w_H` | 1.0 | Hybrid 점수 가중치 |
| `w_T` | 0.3 | Confidence 가중치 |
| `w_type` | 0.5 | 타입 매칭 가중치 |
| `w_ce` | 2.0 | Cross-Encoder 가중치 |
| `top_n` | 20 | 최종 반환 수 |
| `translate_top_n` | 10 | 패턴 번역할 상위 N개 |
| `USER_PREF_MAX` | 5.0 | DB 선호도 최대값 |

---

## 8. 수정 이력

### 2024-XX-XX
- `chat.py`: user_id로 DB에서 user preferences 조회 로직 추가
- `search_engine.py`: min_rating 필터 추가
- `chat.py`: pattern_sources를 활용하여 "[한국인 리뷰]" / "[현지인 리뷰]" 표시 추가
