# src/services/data_models.py
"""
Data models for the title optimizer system
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any

@dataclass
class ProductData:
    """Product information for title optimization"""
    product_id: str
    current_title: str
    brand: Optional[str] = None
    description: Optional[str] = None
    product_type: Optional[str] = None
    manufacturer: Optional[str] = None
    category: Optional[str] = None
    specifications: Optional[Dict[str, str]] = None
    features: Optional[List[str]] = None
    price: Optional[float] = None
    dimensions: Optional[str] = None
    weight: Optional[str] = None
    color: Optional[str] = None
    material: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for easy access"""
        return {
            'product_id': self.product_id,
            'current_title': self.current_title,
            'brand': self.brand,
            'description': self.description,
            'product_type': self.product_type,
            'manufacturer': self.manufacturer,
            'category': self.category,
            'specifications': self.specifications,
            'features': self.features,
            'price': self.price,
            'dimensions': self.dimensions,
            'weight': self.weight,
            'color': self.color,
            'material': self.material
        }

@dataclass
class OptimizationResult:
    """Result of title optimization"""
    original_title: str
    optimized_title: str
    target_search_term: str
    confidence_score: float  # 0.0 to 1.0
    optimization_reasoning: str
    keywords_used: List[str]
    warnings: List[str]
    processing_time: float  # seconds
    model_used: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for display"""
        return {
            'original_title': self.original_title,
            'optimized_title': self.optimized_title,
            'target_search_term': self.target_search_term,
            'confidence_score': self.confidence_score,
            'optimization_reasoning': self.optimization_reasoning,
            'keywords_used': self.keywords_used,
            'warnings': self.warnings,
            'processing_time': self.processing_time,
            'model_used': self.model_used
        }
