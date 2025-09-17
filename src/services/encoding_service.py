# src/services/encoding_service.py
"""
Encoding Service for generating embeddings using LLM models
"""

import os
import pickle
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer
import streamlit as st

class EncodingService:
    """Service for generating and caching text embeddings using LLM models"""
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        self.cache_dir = Path(".cached_encoding")
        self.logger = logging.getLogger(__name__)
        
        # Create cache directory
        self.cache_dir.mkdir(exist_ok=True)
        
        # Initialize model
        self._load_model()
    
    def _load_model(self):
        """Load the sentence transformer model"""
        try:
            self.logger.info(f"Loading model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            self.logger.info(f"Model loaded successfully: {self.model_name}")
        except Exception as e:
            self.logger.error(f"Failed to load model {self.model_name}: {e}")
            raise
    
    def _get_text_hash(self, text: str) -> str:
        """Generate hash for text to use as cache key"""
        # Normalize text: lowercase, strip whitespace
        normalized_text = text.lower().strip()
        return hashlib.sha256(normalized_text.encode('utf-8')).hexdigest()
    
    def _get_cache_path(self, text_hash: str, cache_type: str = "general") -> Path:
        """Get cache file path for a given text hash"""
        cache_file = f"{cache_type}_{text_hash}.pkl"
        return self.cache_dir / cache_file
    
    def _load_from_cache(self, text_hash: str, cache_type: str = "general") -> Optional[np.ndarray]:
        """Load embedding from cache if it exists"""
        cache_path = self._get_cache_path(text_hash, cache_type)
        try:
            if cache_path.exists():
                with open(cache_path, 'rb') as f:
                    cached_data = pickle.load(f)
                    # Verify it's the right model
                    if cached_data.get('model_name') == self.model_name:
                        return cached_data['embedding']
                    else:
                        # Model changed, remove old cache
                        cache_path.unlink()
                        self.logger.info(f"Removed outdated cache for model: {cached_data.get('model_name')}")
        except Exception as e:
            self.logger.warning(f"Failed to load cache {cache_path}: {e}")
        return None
    
    def _save_to_cache(self, text_hash: str, embedding: np.ndarray, cache_type: str = "general"):
        """Save embedding to cache"""
        cache_path = self._get_cache_path(text_hash, cache_type)
        try:
            cache_data = {
                'embedding': embedding,
                'model_name': self.model_name,
                'text_hash': text_hash
            }
            with open(cache_path, 'wb') as f:
                pickle.dump(cache_data, f)
        except Exception as e:
            self.logger.warning(f"Failed to save cache {cache_path}: {e}")
    
    def encode_text(self, text: str, cache_type: str = "general") -> np.ndarray:
        """Encode a single text into embedding vector"""
        if not text or not text.strip():
            # Return zero vector for empty text
            return np.zeros(384)  # all-MiniLM-L6-v2 has 384 dimensions
        
        text_hash = self._get_text_hash(text)
        
        # Try to load from cache first
        cached_embedding = self._load_from_cache(text_hash, cache_type)
        if cached_embedding is not None:
            return cached_embedding
        
        # Generate new embedding
        try:
            embedding = self.model.encode([text])[0]
            # Save to cache
            self._save_to_cache(text_hash, embedding, cache_type)
            return embedding
        except Exception as e:
            self.logger.error(f"Failed to encode text: {e}")
            # Return zero vector as fallback
            return np.zeros(384)
    
    def encode_texts_batch(self, texts: List[str], cache_type: str = "general", 
                          show_progress: bool = True) -> List[np.ndarray]:
        """Encode multiple texts efficiently with caching"""
        if not texts:
            return []
        
        embeddings = []
        texts_to_encode = []
        text_indices = []
        
        # Check cache for each text
        for i, text in enumerate(texts):
            if not text or not text.strip():
                embeddings.append(np.zeros(384))
                continue
            
            text_hash = self._get_text_hash(text)
            cached_embedding = self._load_from_cache(text_hash, cache_type)
            
            if cached_embedding is not None:
                embeddings.append(cached_embedding)
            else:
                embeddings.append(None)  # Placeholder
                texts_to_encode.append(text)
                text_indices.append(i)
        
        # Encode texts that weren't cached
        if texts_to_encode:
            if show_progress:
                progress_bar = st.progress(0)
                status_text = st.empty()
            
            try:
                batch_embeddings = self.model.encode(texts_to_encode, show_progress_bar=False)
                
                # Update embeddings list and cache new embeddings
                for i, (text_idx, embedding) in enumerate(zip(text_indices, batch_embeddings)):
                    embeddings[text_idx] = embedding
                    
                    # Cache the new embedding
                    text_hash = self._get_text_hash(texts[text_idx])
                    self._save_to_cache(text_hash, embedding, cache_type)
                    
                    if show_progress:
                        progress = (i + 1) / len(texts_to_encode)
                        progress_bar.progress(progress)
                        status_text.text(f"Encoding {i + 1}/{len(texts_to_encode)} texts...")
                
                if show_progress:
                    progress_bar.empty()
                    status_text.empty()
                    
            except Exception as e:
                self.logger.error(f"Failed to encode batch: {e}")
                # Fill remaining with zero vectors
                for i in text_indices:
                    if embeddings[i] is None:
                        embeddings[i] = np.zeros(384)
        
        return embeddings
    
    def cosine_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Calculate cosine similarity between two embeddings"""
        try:
            # Normalize embeddings
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            # Calculate cosine similarity
            similarity = np.dot(embedding1, embedding2) / (norm1 * norm2)
            return float(similarity)
        except Exception as e:
            self.logger.error(f"Failed to calculate cosine similarity: {e}")
            return 0.0
    
    def calculate_similarities(self, product_title: str, search_terms: List[str]) -> List[Tuple[str, float]]:
        """Calculate similarities between a product title and multiple search terms"""
        if not product_title or not search_terms:
            return []
        
        # Encode product title
        product_embedding = self.encode_text(product_title, cache_type="product")
        
        # Encode search terms
        search_embeddings = self.encode_texts_batch(search_terms, cache_type="search_term")
        
        # Calculate similarities
        similarities = []
        for search_term, search_embedding in zip(search_terms, search_embeddings):
            similarity = self.cosine_similarity(product_embedding, search_embedding)
            similarities.append((search_term, similarity))
        
        return similarities
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get statistics about cached embeddings"""
        stats = {
            'total_files': 0,
            'product_cache': 0,
            'search_term_cache': 0,
            'general_cache': 0
        }
        
        try:
            for cache_file in self.cache_dir.glob("*.pkl"):
                stats['total_files'] += 1
                
                if cache_file.name.startswith('product_'):
                    stats['product_cache'] += 1
                elif cache_file.name.startswith('search_term_'):
                    stats['search_term_cache'] += 1
                else:
                    stats['general_cache'] += 1
        except Exception as e:
            self.logger.error(f"Failed to get cache stats: {e}")
        
        return stats
    
    def clear_cache(self):
        """Clear all cached embeddings"""
        try:
            for cache_file in self.cache_dir.glob("*.pkl"):
                cache_file.unlink()
            self.logger.info("Cache cleared successfully")
        except Exception as e:
            self.logger.error(f"Failed to clear cache: {e}")
    
    def get_model_info(self) -> Dict[str, str]:
        """Get information about the current model"""
        return {
            'model_name': self.model_name,
            'model_type': 'sentence-transformers',
            'embedding_dimension': '384' if 'all-MiniLM-L6-v2' in self.model_name else 'Unknown',
            'cache_directory': str(self.cache_dir)
        }
