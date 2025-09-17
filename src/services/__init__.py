# src/services/__init__.py
"""
Title Optimizer Services Package
"""

from .data_models import ProductData, OptimizationResult
from .llm_client import LLMClient
from .title_optimizer import TitleOptimizer
from .encoding_service import EncodingService

__all__ = [
    'ProductData',
    'OptimizationResult', 
    'LLMClient',
    'TitleOptimizer',
    'EncodingService'
]

# Package version
__version__ = "1.0.0"