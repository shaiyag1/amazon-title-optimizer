# src/services/__init__.py
"""
Title Optimizer Services Package
"""

from .data_models import ProductData, OptimizationResult
from .llm_client import LLMClient
from .title_optimizer import TitleOptimizer
from .encoding_service import EncodingService
from .description_generator import DescriptionGenerator, DescriptionGenerationResult
from .csv_manager import CSVManager

__all__ = [
    'ProductData',
    'OptimizationResult', 
    'LLMClient',
    'TitleOptimizer',
    'EncodingService',
    'DescriptionGenerator',
    'DescriptionGenerationResult',
    'CSVManager'
]

# Package version
__version__ = "1.0.0"