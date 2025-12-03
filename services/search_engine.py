"""
Restaurant search engine using hybrid search (BM25 + E5) with Cross-Encoder reranking.
Modified from service/cross_encoder.py for backend integration.
"""
import os
from typing import Dict, Any, Optional, List
import numpy as np
import pandas as pd
import pickle

from sentence_transformers import SentenceTransformer, CrossEncoder

from core.config import settings

# ==============================
# 타입 매핑 유틸
# ==============================
CANONICAL_TYPES = {
    "restaurant", "italian_restaurant", "american_restaurant", "mexican_restaurant",
    "pizza_restaurant", "chinese_restaurant", "japanese_restaurant", "thai_restaurant",
    "seafood_restaurant", "greek_restaurant", "french_restaurant", "mediterranean_restaurant",
    "indian_restaurant", "hamburger_restaurant", "korean_restaurant", "steak_house",
    "cafe", "bar", "diner", "bar_and_grill", "deli",
}

TYPE_NORMALIZE_MAP = {
    "steakhouse": "steak_house", "steak house": "steak_house", "steak": "steak_house",
    "pizza": "pizza_restaurant", "pizzeria": "pizza_restaurant",
    "burger": "hamburger_restaurant", "hamburger": "hamburger_restaurant",
    "coffee": "cafe", "cafe": "cafe", "bar": "bar",
    "korean food": "korean_restaurant", "korean": "korean_restaurant",
    "japanese": "japanese_restaurant", "chinese": "chinese_restaurant", "thai": "thai_restaurant",
}

# Aspect 매핑
ASPECT_NAME_TO_COL = {
    "food": "Z_S_food_avg",
    "service": "Z_S_service_avg",
    "ambience": "Z_S_ambience_avg",
    "price": "Z_S_price_avg",
    "hygiene": "Z_S_hygiene_avg",
    "waiting": "Z_S_waiting_avg",
    "accessibility": "Z_S_accessibility_avg",
}


class SearchEngine:
    """Hybrid search engine with BM25, E5 embeddings, and Cross-Encoder reranking."""
    
    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize search engine.
        
        Args:
            data_dir: Directory containing data files (emb_e5.npy, bm25.pkl, df_dedup_enriched.parquet).
                      Defaults to settings.SEARCH_DATA_DIR if not specified.
        """
        self.data_dir = data_dir or settings.SEARCH_DATA_DIR
        self.model_name = "intfloat/e5-large-v2"
        self.ce_model_name = "cross-encoder/ms-marco-MiniLM-L-6-v2"
        
        # Lazy loading flags
        self._df = None
        self._emb = None
        self._bm25 = None
        self._query_model = None
        self._ce_model = None
    
    @property
    def df_dedup(self) -> pd.DataFrame:
        """Lazy load restaurant dataframe."""
        if self._df is None:
            path = os.path.join(self.data_dir, "df_dedup_enriched.parquet")
            print(f"[SearchEngine] Loading restaurant data from {path}")
            self._df = pd.read_parquet(path)
            print(f"[SearchEngine] Loaded {len(self._df)} restaurants")
        return self._df
    
    @property
    def emb_e5(self) -> np.ndarray:
        """Lazy load E5 embeddings."""
        if self._emb is None:
            path = os.path.join(self.data_dir, "emb_e5.npy")
            print(f"[SearchEngine] Loading E5 embeddings from {path}")
            self._emb = np.load(path)
            print(f"[SearchEngine] Loaded embeddings with shape {self._emb.shape}")
        return self._emb
    
    @property
    def bm25(self):
        """Lazy load BM25 index."""
        if self._bm25 is None:
            path = os.path.join(self.data_dir, "bm25.pkl")
            print(f"[SearchEngine] Loading BM25 index from {path}")
            with open(path, "rb") as f:
                self._bm25 = pickle.load(f)
            print(f"[SearchEngine] Loaded BM25 index with corpus size {self._bm25.corpus_size}")
        return self._bm25
    
    @property
    def query_model(self) -> SentenceTransformer:
        """Lazy load query encoder model."""
        if self._query_model is None:
            print(f"[SearchEngine] Loading query encoder: {self.model_name}")
            self._query_model = SentenceTransformer(self.model_name)
            print("[SearchEngine] Query encoder loaded")
        return self._query_model
    
    @property
    def ce_model(self) -> CrossEncoder:
        """Lazy load cross-encoder model."""
        if self._ce_model is None:
            print(f"[SearchEngine] Loading cross encoder: {self.ce_model_name}")
            self._ce_model = CrossEncoder(self.ce_model_name)
            print("[SearchEngine] Cross encoder loaded")
        return self._ce_model
    
    # ==============================
    # Utility Functions
    # ==============================
    
    @staticmethod
    def minmax_normalize(x: np.ndarray) -> np.ndarray:
        """MinMax normalization."""
        x = np.asarray(x, dtype=float)
        x_min, x_max = x.min(), x.max()
        if x_max == x_min:
            return np.zeros_like(x)
        return (x - x_min) / (x_max - x_min)
    
    @staticmethod
    def normalize_desired_types(raw_types) -> List[str]:
        """Normalize restaurant types to canonical forms."""
        if not raw_types:
            return []
        
        if isinstance(raw_types, str):
            raw_list = [raw_types]
        else:
            raw_list = list(raw_types)
        
        normed = []
        for t in raw_list:
            if not t:
                continue
            t_low = t.strip().lower()
            
            if t_low in TYPE_NORMALIZE_MAP:
                normed.append(TYPE_NORMALIZE_MAP[t_low])
            elif t_low in CANONICAL_TYPES:
                normed.append(t_low)
            elif (not t_low.endswith("_restaurant")) and (t_low + "_restaurant") in CANONICAL_TYPES:
                normed.append(t_low + "_restaurant")
        
        return list(dict.fromkeys(normed))  # Remove duplicates
    
    @staticmethod
    def normalize_aspect_weights(aspect_weights: Dict[str, float]) -> Dict[str, float]:
        """Map aspect names to Z-score columns and L1 normalize."""
        mapped = {}
        for name, w in aspect_weights.items():
            col = ASPECT_NAME_TO_COL.get(name)
            if col is not None:
                mapped[col] = float(w)
        
        total = sum(mapped.values())
        if total > 0:
            mapped = {k: v / total for k, v in mapped.items()}
        return mapped
    
    @staticmethod
    def build_user_pref_text(aspect_weights: Dict[str, float]) -> str:
        """Build user preference text for cross-encoder input."""
        if not aspect_weights:
            return ""
        
        parts = []
        if aspect_weights.get("food", 0) > 0:
            parts.append(f"Food importance: {aspect_weights['food']:.2f}")
        if aspect_weights.get("service", 0) > 0:
            parts.append(f"Service importance: {aspect_weights['service']:.2f}")
        if aspect_weights.get("ambience", 0) > 0:
            parts.append(f"Ambience importance: {aspect_weights['ambience']:.2f}")
        if aspect_weights.get("price", 0) > 0:
            parts.append(f"Price importance: {aspect_weights['price']:.2f}")
        if aspect_weights.get("hygiene", 0) > 0:
            parts.append(f"Hygiene importance: {aspect_weights['hygiene']:.2f}")
        if aspect_weights.get("waiting", 0) > 0:
            parts.append(f"Waiting importance: {aspect_weights['waiting']:.2f}")
        if aspect_weights.get("accessibility", 0) > 0:
            parts.append(f"Accessibility importance: {aspect_weights['accessibility']:.2f}")
        
        if not parts:
            return ""
        return "User preferences: " + "; ".join(parts)
    
    @staticmethod
    def _has_desired_type(types_final_value, desired_types) -> bool:
        """Check if restaurant has any of the desired types."""
        if not isinstance(types_final_value, str):
            return False
        tokens = [t.strip() for t in types_final_value.split("|") if t.strip()]
        return any(t in tokens for t in desired_types)
    
    # ==============================
    # Search Functions
    # ==============================
    
    def embed_query(self, query: str) -> np.ndarray:
        """Generate E5 embedding for query."""
        vec = self.query_model.encode([query], normalize_embeddings=True)[0]
        return vec.astype(np.float32)
    
    def get_bm25_scores(self, query: str) -> np.ndarray:
        """Get BM25 scores for all documents."""
        tokens = query.lower().split()
        scores = np.array(self.bm25.get_scores(tokens), dtype=np.float32)
        return scores
    
    def get_e5_scores(self, query: str) -> np.ndarray:
        """Get E5 cosine similarity scores for all documents."""
        q_vec = self.embed_query(query)
        scores = self.emb_e5 @ q_vec
        return scores
    
    def compute_hybrid_scores(self, query: str, w_bm25: float = 0.1, w_e5: float = 0.9):
        """Compute hybrid scores combining BM25 and E5."""
        scores_b = self.get_bm25_scores(query)
        scores_e = self.get_e5_scores(query)
        
        s_b_norm = self.minmax_normalize(scores_b)
        s_e_norm = self.minmax_normalize(scores_e)
        
        s_hybrid = w_bm25 * s_b_norm + w_e5 * s_e_norm
        return s_hybrid, scores_b, scores_e
    
    def build_candidate_pool(self, scores_b: np.ndarray, scores_e: np.ndarray,
                            top_k_bm25: int = 60, top_k_e5: int = 60) -> np.ndarray:
        """Build candidate pool from top BM25 and E5 results."""
        idx_b = np.argsort(scores_b)[::-1][:top_k_bm25]
        idx_e = np.argsort(scores_e)[::-1][:top_k_e5]
        pool_idx = np.unique(np.concatenate([idx_b, idx_e]))
        return pool_idx
    
    def apply_filters(self, df_candidates: pd.DataFrame,
                     filters: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """Apply hard filters (borough, min_rating)."""
        if not filters:
            return df_candidates
        
        df = df_candidates.copy()
        
        # Borough filter
        if "borough_en" in filters and filters["borough_en"]:
            df = df[df["borough_en"] == filters["borough_en"]]
        
        # Minimum rating filter
        if "min_rating" in filters and filters["min_rating"] is not None:
            min_rating = float(filters["min_rating"])
            if "rating" in df.columns:
                # Keep rows with rating >= min_rating or rating is NaN (to not exclude unrated)
                df = df[(df["rating"] >= min_rating) | (df["rating"].isna())]
        
        return df
    
    def compute_cross_encoder_scores(self, query: str, df_pool: pd.DataFrame,
                                    aspect_weights: Dict[str, float]) -> np.ndarray:
        """
        Compute cross-encoder scores for candidate pool.
        
        Args:
            query: English search query
            df_pool: Candidate dataframe
            aspect_weights: User preference weights
            
        Returns:
            MinMax normalized cross-encoder scores
        """
        # Build query with user preferences
        user_pref_text = self.build_user_pref_text(aspect_weights)
        if user_pref_text:
            query_for_ce = f"{query} [PREF] {user_pref_text}"
        else:
            query_for_ce = query
        
        # Build query-document pairs
        pairs = []
        for _, row in df_pool.iterrows():
            doc_text = row.get("bm25_text", "")
            pairs.append((query_for_ce, doc_text))
        
        # Get cross-encoder scores
        ce_scores = self.ce_model.predict(pairs)
        ce_scores = np.asarray(ce_scores, dtype=float)
        
        # MinMax normalize
        return self.minmax_normalize(ce_scores)
    
    # ==============================
    # Main Rerank Function
    # ==============================
    
    def rerank(self, query: str, aspect_weights: Dict[str, float],
              filters: Optional[Dict[str, Any]] = None,
              top_k_bm25: int = 60, top_k_e5: int = 60,
              w_bm25: float = 0.1, w_e5: float = 0.9,
              w_H: float = 1.0, w_T: float = 0.3, w_type: float = 0.5,
              w_ce: float = 2.0, top_n: int = 20) -> pd.DataFrame:
        """
        Main re-ranking function with Cross-Encoder.
        
        Args:
            query: English search query
            aspect_weights: User preference weights
            filters: Optional filters (borough_en, desired_types, min_rating)
            top_k_bm25: Top K from BM25
            top_k_e5: Top K from E5
            w_bm25: Weight for BM25
            w_e5: Weight for E5
            w_H: Weight for hybrid score
            w_T: Weight for confidence
            w_type: Weight for type matching
            w_ce: Weight for cross-encoder score
            top_n: Number of results to return
            
        Returns:
            DataFrame with top N restaurants sorted by Score_final
        """
        # 1. Compute hybrid scores
        S_hybrid, scores_b, scores_e = self.compute_hybrid_scores(query, w_bm25, w_e5)
        
        # 2. Build candidate pool
        pool_idx = self.build_candidate_pool(scores_b, scores_e, top_k_bm25, top_k_e5)
        df_pool = self.df_dedup.iloc[pool_idx].copy()
        df_pool["S_hybrid"] = S_hybrid[pool_idx]
        
        # 3. Apply filters
        df_filtered = self.apply_filters(df_pool, filters)
        if df_filtered.empty:
            df_filtered = df_pool  # Ignore filters if no results
        
        # 4. Compute type matching score
        desired_types = []
        if filters and "desired_types" in filters and filters["desired_types"]:
            dt = filters["desired_types"]
            desired_types = [dt] if isinstance(dt, str) else list(dt)
        
        if desired_types:
            df_filtered["S_type"] = df_filtered["types_final"].apply(
                lambda ts: 1.0 if self._has_desired_type(ts, desired_types) else 0.0
            )
        else:
            df_filtered["S_type"] = 0.0
        
        # 5. Compute cross-encoder scores
        ce_scores = self.compute_cross_encoder_scores(query, df_filtered, aspect_weights)
        df_filtered["S_ce"] = ce_scores
        
        # 6. Compute final score (using cross-encoder instead of aspect score)
        df_filtered["Score_final"] = (
            w_H * df_filtered["S_hybrid"].values +
            w_T * df_filtered["S_conf"].values +
            w_type * df_filtered["S_type"].values +
            w_ce * df_filtered["S_ce"].values
        )
        
        # 7. Sort and return top N
        df_result = df_filtered.sort_values("Score_final", ascending=False).head(top_n)
        return df_result


# Global instance (singleton pattern)
_search_engine: Optional[SearchEngine] = None


def get_search_engine(data_dir: Optional[str] = None) -> SearchEngine:
    """
    Get or create global search engine instance.
    
    Args:
        data_dir: Directory containing data files. Defaults to settings.SEARCH_DATA_DIR.
        
    Returns:
        SearchEngine singleton instance
    """
    global _search_engine
    if _search_engine is None:
        _search_engine = SearchEngine(data_dir=data_dir)
    return _search_engine
