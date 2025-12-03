"""
Translation service using OpenAI API.
Translates Korean queries to English for RAG search.
"""
import openai
from typing import Optional

from core.config import settings


# Initialize OpenAI client
client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)


async def translate_to_english(text: str) -> str:
    """
    Translate Korean text to English using OpenAI API.
    
    Args:
        text: Korean text to translate
        
    Returns:
        Translated English text
        
    Raises:
        Exception: If translation fails
    """
    if not text.strip():
        return text
    
    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a translator. Translate the following Korean text to English. "
                               "If the text is already in English, return it as is. "
                               "Only return the translated text without any explanation."
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        translated = response.choices[0].message.content.strip()
        return translated
        
    except Exception as e:
        # Log error and return original text as fallback
        print(f"Translation error: {e}")
        return text


def is_korean(text: str) -> bool:
    """
    Check if text contains Korean characters.
    
    Args:
        text: Text to check
        
    Returns:
        True if text contains Korean characters
    """
    for char in text:
        if '\uAC00' <= char <= '\uD7A3' or '\u1100' <= char <= '\u11FF':
            return True
    return False
