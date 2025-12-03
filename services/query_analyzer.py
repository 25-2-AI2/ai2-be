"""
Query analyzer using LLM for Korean natural language queries.
Extracts English query, filters, and aspect weights.
Includes pattern extraction and translation utilities.
"""
import json
import re

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import settings


# Initialize OpenAI client using config
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


# ==============================
# System Prompt for Query Analysis
# ==============================
COMBINED_SYSTEM_PROMPT = """
You are a query understanding engine for a New York City restaurant search system.

Given a Korean user query, you must output a single JSON object with:
- "query_en": natural English search query
- "filters": {
    "borough_en": string or null,          // One of ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"]
    "desired_types": array of strings or null, // e.g. ["pizza_restaurant"]
    "min_rating": float or null
  }
- "aspect_weights": {
    "food": float or null,
    "service": float or null,
    "ambience": float or null,
    "price": float or null,
    "hygiene": float or null,
    "waiting": float or null,
    "accessibility": float or null
  }

-------------------------------
RULES
-------------------------------

### 1. "query_en"
- Translate the Korean query into a concise, natural English search query.
- Preserve all nuances: salty, spicy, sweet, portion size, cleanliness, ambience, budget, etc.
- Do NOT add details not clearly implied by the user.

### 2. "filters"
- Detect borough ONLY if explicitly mentioned:
  - 맨해튼 → "Manhattan"
  - 브루클린 → "Brooklyn"
  - 퀸즈 → "Queens"
  - 브롱크스 → "Bronx"
  - 스태튼 아일랜드 → "Staten Island"
- Detect main cuisine/type (피자, 파스타, 이탈리안, 한식, 라멘, 카페 등)
  → Put them into "desired_types" (soft preference)
  → NEVER treat these as hard filters.
  - "desired_types"에 넣는 값은 가능하면 다음 형태를 따라라:
  - "pizza_restaurant"
  - "italian_restaurant"
  - "japanese_restaurant"
  - "steak_house"
  - "thai_restaurant"
  - "hamburger_restaurant"
  - "cafe"
  - "bar"
  - ...
- 만약 정확한 타입이 헷갈리면 null 로 둬라.

- If the query does not specify borough or type, set them to null.
- Set "min_rating" ONLY if the user explicitly mentions rating (e.g., "4점 이상").
- Never infer rating from vague words like "좋은", "괜찮은".

### 3. "aspect_weights"
- **CRITICAL: Set null for aspects NOT mentioned in the query.**
- When mentioned, values must be between 0.0 and 1.0.
- 0.0 = explicitly stated as NOT important (e.g., "가격은 상관없어", "비싸도 괜찮아")
- 0.1~1.0 = mentioned with varying importance levels
- null = NOT mentioned at all (will use user's stored preferences)

Extract from implied meaning:
  - "조용한 분위기", "데이트하기 좋은" → ambience: 0.7~1.0
  - "가성비", "저렴한", "가격대 괜찮은" → price: 0.7~1.0
  - "가격은 상관없어", "비싸도 괜찮아", "돈은 좀 써도 돼" → price: 0.0~0.2 (LOW, not null!)
  - "맛있다", "짜다", "달다", "부드럽다", "진하다" → food: 0.7~1.0
  - "직원 친절" → service: 0.7~1.0
  - "깨끗한", "위생" → hygiene: 0.7~1.0
  - "웨이팅 짧게", "바로 들어갈" → waiting: 0.7~1.0
  - "지하철역 가까운", "접근성 좋은" → accessibility: 0.7~1.0

**Examples:**
- "맛있는 이탈리안" → food: 0.8, others: null
- "가격 비싸도 분위기 좋은 곳" → price: 0.1, ambience: 0.9, others: null
- "가성비 좋고 맛있는 피자" → price: 0.8, food: 0.8, others: null
- "아무거나 추천해줘" → all: null

-------------------------------
OUTPUT FORMAT
-------------------------------
- MUST output valid JSON only.
- NO explanation outside the JSON.
"""


@retry(wait=wait_exponential(min=1, max=8), stop=stop_after_attempt(3))
async def analyze_query_ko(query_ko: str) -> dict:
    """
    Analyze Korean query using LLM.
    
    Args:
        query_ko: Korean natural language query
        
    Returns:
        Dictionary with:
        - query_en: English translated query
        - filters: Dict with borough_en, desired_types, min_rating
        - aspect_weights: Dict with 7 aspect scores (float or null)
    """
    resp = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        temperature=0.1,
        timeout=12,
        messages=[
            {"role": "system", "content": COMBINED_SYSTEM_PROMPT},
            {"role": "user", "content": query_ko},
        ],
    )
    content = resp.choices[0].message.content.strip()
    return json.loads(content)


# ==============================
# Pattern Translation
# ==============================
@retry(wait=wait_exponential(min=1, max=8), stop=stop_after_attempt(3))
async def translate_pattern_to_ko(text: str) -> str:
    """
    Translate English reviewer pattern summary to natural Korean.
    
    Args:
        text: English pattern text
        
    Returns:
        Korean translated pattern
    """
    if not text:
        return ""
    
    resp = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        temperature=0.3,
        timeout=12,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a professional Korean translator for a restaurant review app. "
                    "Given an English summary of reviewer patterns, rewrite only the content in natural Korean, "
                    "short and friendly, as if explaining to a Korean friend. "
                    "IMPORTANT: If the text contains section headers such as '[Korean Reviewer Pattern]' or "
                    "'[Non-Korean Reviewer Pattern]', DO NOT translate or remove them. "
                    "Leave those headers exactly as they are and translate only the sentences below."
                ),
            },
            {"role": "user", "content": text},
        ],
    )
    return resp.choices[0].message.content.strip()


# ==============================
# Utility: Extract Sections from Summary
# ==============================
def extract_section(summary: str, section_name: str) -> str:
    """
    Extract a specific section from restaurant summary.
    
    Args:
        summary: Full summary text
        section_name: Section name to extract
        
    Returns:
        Extracted section content
    """
    if not isinstance(summary, str):
        return ""
    
    pattern = rf"\[{re.escape(section_name)}\](.*?)(\n\[[A-Za-z ]+\]|\Z)"
    m = re.search(pattern, summary, flags=re.DOTALL)
    if not m:
        return ""
    
    return m.group(1).strip()


def get_korean_pattern(summary: str) -> str:
    """
    Extract Korean Reviewer Pattern from summary.
    
    Args:
        summary: Restaurant summary text
        
    Returns:
        Korean reviewer pattern or empty string
    """
    section = extract_section(summary, "Korean Reviewer Pattern")
    if not section:
        return ""
    if section.strip().lower().startswith("no notable mentions"):
        return ""
    return section


def get_preferred_pattern(summary: str) -> tuple:
    """
    Get the preferred reviewer pattern from summary.
    
    Tries Korean reviewer pattern first, falls back to Non-Korean pattern.
    
    Args:
        summary: Restaurant summary text
        
    Returns:
        Tuple of (pattern_source, pattern_text):
        - ("korean", text): Korean reviewer pattern found
        - ("non_korean", text): Non-Korean reviewer pattern found
        - ("", ""): No pattern found
    """
    # 1. Try Korean reviewer pattern first
    kr = extract_section(summary, "Korean Reviewer Pattern")
    if kr:
        if not kr.strip().lower().startswith("no notable mentions"):
            return "korean", kr
    
    # 2. Fall back to Non-Korean reviewer pattern
    non_kr = extract_section(summary, "Non-Korean Reviewer Pattern")
    if non_kr:
        if not non_kr.strip().lower().startswith("no notable mentions"):
            return "non_korean", non_kr
    
    # 3. No pattern found
    return "", ""
