# src/services/description_generator.py
"""
Description Generator for Amazon products
"""

import time
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from .llm_client import LLMClient
from .data_models import ProductData

@dataclass
class DescriptionGenerationResult:
    """Result of description generation"""
    original_title: str
    generated_description: str
    confidence_score: float
    generation_reasoning: str
    keywords_used: List[str]
    warnings: List[str]
    processing_time: float
    model_used: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for display"""
        return {
            'original_title': self.original_title,
            'generated_description': self.generated_description,
            'confidence_score': self.confidence_score,
            'generation_reasoning': self.generation_reasoning,
            'keywords_used': self.keywords_used,
            'warnings': self.warnings,
            'processing_time': self.processing_time,
            'model_used': self.model_used
        }

class DescriptionGenerator:
    """Generates product descriptions using LLM"""
    
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.logger = logging.getLogger(__name__)
        self._load_prompts()
    
    def _load_prompts(self):
        """Load description generation prompt templates"""
        self.description_prompt = """
You are an expert Amazon product description writer. Generate a compelling, SEO-optimized product description that would perform well on Amazon.

PRODUCT INFORMATION:
- Product ID: {product_id}
- Title: {title}
- Brand: {brand}
- Product Type: {product_type}
- Features: {features}
- Category: {category}

DESCRIPTION REQUIREMENTS:
- 150-300 words (Amazon-optimized length)
- Include key product benefits and features
- Use persuasive, conversion-focused language
- Include relevant keywords naturally
- Structure with clear paragraphs
- End with a compelling call-to-action

RESPONSE FORMAT:
Provide your response in this exact format:

GENERATED_DESCRIPTION: [Your generated description here]
CONFIDENCE: [Score from 0.0 to 1.0]
REASONING: [Brief explanation of your approach]
KEYWORDS_USED: [List of keywords incorporated]
WARNINGS: [Any concerns or limitations, or "None"]

Now generate the product description:
"""
    
    def generate_description(self, product_data: ProductData) -> DescriptionGenerationResult:
        """Generate a product description"""
        start_time = time.time()
        
        try:
            # Prepare the prompt
            prompt = self._prepare_prompt(product_data)
            
            # Call LLM
            response = self.llm_client.generate_response(prompt)
            
            # Parse response
            result = self._parse_response(response, product_data, start_time)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error generating description: {e}")
            return self._create_error_result(product_data, str(e), start_time)
    
    def _prepare_prompt(self, product_data: ProductData) -> str:
        """Prepare the description generation prompt"""
        features_str = ""
        if product_data.features:
            if isinstance(product_data.features, list):
                features_str = ", ".join(product_data.features)
            else:
                features_str = str(product_data.features)
        
        return self.description_prompt.format(
            product_id=product_data.product_id,
            title=product_data.current_title,
            brand=product_data.brand or "Unknown",
            product_type=product_data.product_type or "Product",
            features=features_str or "No features provided",
            category=product_data.category or "General"
        )
    
    def _parse_response(self, response: str, product_data: ProductData, start_time: float) -> DescriptionGenerationResult:
        """Parse LLM response into structured result"""
        lines = response.strip().split('\n')
        
        # Initialize with defaults
        generated_description = ""
        confidence_score = 0.5
        generation_reasoning = "Unable to parse response"
        keywords_used = []
        warnings = []
        
        # Parse each line with multi-line support
        i = 0
        field_keywords = ['GENERATED_DESCRIPTION', 'CONFIDENCE', 'REASONING', 'KEYWORDS_USED', 'WARNINGS']
        
        while i < len(lines):
            line = lines[i].strip()
            
            if 'GENERATED_DESCRIPTION' in line and ':' in line:
                # Capture multi-line description
                desc_parts = [line.split(':', 1)[1].strip()]
                i += 1
                while i < len(lines):
                    next_line = lines[i].strip()
                    if next_line and any(field + ':' in next_line.upper() for field in field_keywords):
                        break
                    if next_line:
                        desc_parts.append(next_line)
                    i += 1
                generated_description = '\n'.join(desc_parts).strip()
                generated_description = generated_description.replace('**', '').replace('***', '').strip()
                continue
                
            elif 'CONFIDENCE' in line and ':' in line:
                try:
                    confidence_score = float(line.split(':', 1)[1].strip())
                except ValueError:
                    confidence_score = 0.5
                i += 1
                
            elif 'REASONING' in line and ':' in line:
                # Capture multi-line reasoning
                reasoning_parts = [line.split(':', 1)[1].strip()]
                i += 1
                while i < len(lines):
                    next_line = lines[i].strip()
                    if next_line and any(field + ':' in next_line.upper() for field in field_keywords):
                        break
                    if next_line:
                        reasoning_parts.append(next_line)
                    i += 1
                generation_reasoning = ' '.join(reasoning_parts).strip()
                generation_reasoning = generation_reasoning.replace('**', '').replace('***', '').strip()
                continue
                
            elif 'KEYWORDS_USED' in line and ':' in line:
                # Capture multi-line keywords
                keywords_parts = [line.split(':', 1)[1].strip()]
                i += 1
                while i < len(lines):
                    next_line = lines[i].strip()
                    if next_line and any(field + ':' in next_line.upper() for field in field_keywords):
                        break
                    if next_line:
                        keywords_parts.append(next_line)
                    i += 1
                keywords_str = ' '.join(keywords_parts).strip()
                keywords_used = [kw.strip() for kw in keywords_str.split(',') if kw.strip()]
                continue
                
            elif 'WARNINGS' in line and ':' in line:
                # Capture multi-line warnings
                warnings_parts = [line.split(':', 1)[1].strip()]
                i += 1
                while i < len(lines):
                    next_line = lines[i].strip()
                    if next_line and any(field + ':' in next_line.upper() for field in field_keywords):
                        break
                    if next_line:
                        warnings_parts.append(next_line)
                    i += 1
                warnings_str = ' '.join(warnings_parts).strip()
                if warnings_str.lower() not in ['none', 'n/a', '']:
                    warnings = [w.strip() for w in warnings_str.split(',') if w.strip()]
                else:
                    warnings = []
                continue
            else:
                i += 1
        
        return DescriptionGenerationResult(
            original_title=product_data.current_title,
            generated_description=generated_description,
            confidence_score=confidence_score,
            generation_reasoning=generation_reasoning,
            keywords_used=keywords_used,
            warnings=warnings,
            processing_time=time.time() - start_time,
            model_used=self.llm_client.model_name
        )
    
    def _create_error_result(self, product_data: ProductData, error_msg: str, start_time: float) -> DescriptionGenerationResult:
        """Create error result when generation fails"""
        return DescriptionGenerationResult(
            original_title=product_data.current_title,
            generated_description="",
            confidence_score=0.0,
            generation_reasoning=f"Error: {error_msg}",
            keywords_used=[],
            warnings=[error_msg],
            processing_time=time.time() - start_time,
            model_used="error"
        )

