# src/services/title_optimizer.py
"""
Title Optimizer for Amazon products
"""

import time
import logging
from typing import List, Dict, Any
from .data_models import ProductData, OptimizationResult
from src.services.llm_client import LLMClient


class TitleOptimizer:
    """Optimizes product titles for better search term matching"""
    
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.logger = logging.getLogger(__name__)
        
        # Load prompt templates
        self._load_prompts()
    
    def _load_prompts(self):
        """Load optimization prompt templates"""
        
        # Default: Keep Max Info Prompt (prioritizes preserving original content)
        self.optimization_prompt = """
You are an expert Amazon product title optimizer. Your PRIMARY GOAL is to preserve as much of the original title as possible while incorporating target search terms naturally.

PRODUCT INFORMATION:
- Product ID: {product_id}
- Current Title: {current_title}
- Brand: {brand}
- Description: {description}
- Product Type: {product_type}
- Manufacturer: {manufacturer}
- Category: {category}
- Features: {features}

{search_terms_instruction}

CRITICAL PRESERVATION RULES (in order of priority):
1. PRESERVE FIRST: Keep 90%+ of the original title content
2. LENGTH PRESERVATION: Keep the optimized title similar in length to the original (within 20% difference)
3. CONTENT PRESERVATION: Don't remove important specifications, quantities, or features
4. STRUCTURE PRESERVATION: Maintain the original title's structure and flow
5. HONESTY: Never add features that don't exist in the original

OPTIMIZATION STRATEGY:
- ADDITIVE APPROACH: Add target search terms to existing content
- ENHANCEMENT APPROACH: Replace weak/generic words with target terms
- INTEGRATION APPROACH: Weave target terms into existing phrases
- MINIMAL REMOVAL: Only remove redundant words if absolutely necessary

LENGTH GUIDELINES:
- If original title is under 150 chars: Keep optimized title under 200 chars
- If original title is 150-200 chars: Keep optimized title under 250 chars
- If original title exceeds 200 chars: Keep optimized title within 20% of original length

EXAMPLES OF GOOD PRESERVATION:
Original: "Purity Eyeglass Len Cleaner Kit - Includes Eyeglass Lens Cleaner Kit (2x8oz & 1x2oz Lens Cleaner)& 6 Microfiber Lens Cleaning Cloths - for Eyeglasses,Screens,Lenses, Phones and Other Delicate Surfaces"
Target: "eyeglass cleaner refill, Spray"
Good: "Purity Eyeglass Lens Cleaner Kit Refill Spray - Includes Eyeglass Lens Cleaner Kit (2x8oz & 1x2oz Lens Cleaner) & 6 Microfiber Lens Cleaning Cloths - for Eyeglasses, Screens, Lenses, Phones and Other Delicate Surfaces"
Bad: "Eyeglass Lens Cleaner Kit Refill Spray - Includes 2x8oz & 1x2oz Lens Cleaner, 6 Microfiber Cloths" (loses too much)

RESPONSE FORMAT:
Provide your response in this exact format:

OPTIMIZED_TITLE: [Your optimized title here]
CONFIDENCE: [Score from 0.0 to 1.0]
REASONING: [Brief explanation focusing on what you preserved vs. what you changed]
PRESERVATION_SCORE: [Percentage of original content preserved, 0-100]
KEYWORDS_USED: [List of keywords you incorporated]
CHANGES_MADE: [Specific changes: Added/Removed/Moved elements]
WARNINGS: [Any concerns or limitations, or "None" if no concerns]

SUCCESS METRICS:
- High preservation score (80%+)
- Similar length to original
- All target search terms incorporated
- Original specifications maintained

Now optimize the title while preserving maximum original content:
"""

        # Alternative: Standard Prompt (more aggressive optimization)
        self.standard_optimization_prompt = """
You are an expert Amazon product title optimizer. Your task is to optimize a product title to better match a target search term while maintaining honesty and accuracy.

PRODUCT INFORMATION:
- Product ID: {product_id}
- Current Title: {current_title}
- Brand: {brand}
- Description: {description}
- Product Type: {product_type}
- Manufacturer: {manufacturer}
- Category: {category}
- Features: {features}

{search_terms_instruction}

OPTIMIZATION RULES:
1. Be completely honest - don't add features that don't exist
2. Keep the brand name if it exists
3. Include the target search term(s) naturally in the title
4. Maintain Amazon title best practices (under 200 characters)
5. Keep important specifications and key features
6. Don't make false claims or misleading statements
7. Preserve the core product identity
8. Use natural language that customers would search for

RESPONSE FORMAT:
Provide your response in this exact format:

OPTIMIZED_TITLE: [Your optimized title here]
CONFIDENCE: [Score from 0.0 to 1.0]
REASONING: [Brief explanation of your optimization choices]
KEYWORDS_USED: [List of keywords you incorporated]
WARNINGS: [Any concerns or limitations, or "None" if no concerns]

Now optimize the title:
"""
    def _load_prompts2(self):
        """Load optimization prompt templates"""
        self.optimization_prompt = """
    You are an expert Amazon product title optimizer. Your primary task is to optimize a product title to better match a target search term while PRESERVING AS MUCH OF THE ORIGINAL TITLE AS POSSIBLE.

    PRODUCT INFORMATION:
    - Product ID: {product_id}
    - Current Title: {current_title}
    - Brand: {brand}
    - Description: {description}
    - Product Type: {product_type}
    - Manufacturer: {manufacturer}
    - Category: {category}
    - Features: {features}

    TARGET SEARCH TERM: {target_search_term}

    OPTIMIZATION STRATEGY:
    1. PRESERVATION FIRST: Keep as much of the original title as possible
    2. STRATEGIC INTEGRATION: Add or emphasize the target search term naturally
    3. MAINTAIN ORDER: Try to keep important elements in similar positions
    4. APPEND WHEN POSSIBLE: If the target search term doesn't naturally fit, consider adding it at the end

    OPTIMIZATION RULES (in order of priority):
    1. Be completely honest - don't add features that don't exist
    2. PRESERVE the existing brand name, model numbers, and key specifications
    3. KEEP existing important keywords and features from the original title
    4. INTEGRATE the target search term naturally without removing valuable existing content
    5. Maintain Amazon title best practices (under 200 characters)
    6. Only REMOVE words from the original if they are redundant or if space is critically needed
    7. REORDER only if it significantly improves search relevance
    8. Don't make false claims or misleading statements

    OPTIMIZATION APPROACHES (try in this order):
    A. ADDITIVE: Add the target search term to the existing title
    B. ENHANCEMENT: Replace weak/generic words with the target search term
    C. INTEGRATION: Weave the target search term into existing phrases
    D. MINIMAL RESTRUCTURE: Only if A, B, C don't work well

    EXAMPLES OF GOOD PRESERVATION:
    - Original: "Philips LED Light Bulb 60W Equivalent Daylight 5000K"
    - Target: "outdoor lighting"
    - Good: "Philips LED Light Bulb 60W Equivalent Daylight 5000K Outdoor Lighting"
    - Bad: "Philips Outdoor Lighting LED Bulb" (loses too much original content)

    RESPONSE FORMAT:
    Provide your response in this exact format:

    OPTIMIZED_TITLE: [Your optimized title here]
    CONFIDENCE: [Score from 0.0 to 1.0]
    REASONING: [Brief explanation focusing on what you preserved vs. what you changed]
    PRESERVATION_SCORE: [Percentage of original title content preserved, 0-100]
    KEYWORDS_USED: [List of keywords you incorporated]
    CHANGES_MADE: [Specific changes: Added/Removed/Moved elements]
    WARNINGS: [Any concerns or limitations, or "None" if no concerns]

    REMEMBER: Your success is measured not just by search term integration, but by how well you preserve the valuable information already in the original title.

    Now optimize the title:
    """
    def optimize_title(self, product_data: ProductData, target_search_terms: List[str]) -> OptimizationResult:
        """Optimize product title for target search terms"""
        start_time = time.time()
        
        try:
            # Prepare the prompt
            prompt = self._prepare_prompt(product_data, target_search_terms)
            
            # Get LLM response
            search_terms_str = ", ".join(target_search_terms)
            self.logger.info(f"Optimizing title for product {product_data.product_id} with search terms: {search_terms_str}")
            response = self.llm_client.generate_response(prompt)
            
            # Parse the response
            result = self._parse_response(response, product_data, target_search_terms, start_time)
            
            self.logger.info(f"Title optimization completed for product {product_data.product_id}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error optimizing title: {e}")
            raise
    
    def _prepare_prompt(self, product_data: ProductData, target_search_terms: List[str]) -> str:
        """Prepare the optimization prompt"""
        # Convert features list to string
        features_str = ", ".join(product_data.features) if product_data.features else "None"
        
        # Format search terms for the prompt
        if len(target_search_terms) == 1:
            search_terms_display = target_search_terms[0]
            search_terms_instruction = f"TARGET SEARCH TERM: {target_search_terms[0]}"
        else:
            search_terms_display = ", ".join(target_search_terms)
            search_terms_instruction = f"TARGET SEARCH TERMS: {', '.join(target_search_terms)}\n\nIMPORTANT: You must incorporate ALL of these search terms naturally into the optimized title. Prioritize the most important/relevant terms but try to include as many as possible."
        
        return self.optimization_prompt.format(
            product_id=product_data.product_id,
            current_title=product_data.current_title,
            brand=product_data.brand or "Not specified",
            description=product_data.description or "Not provided",
            product_type=product_data.product_type or "Not specified",
            manufacturer=product_data.manufacturer or "Not specified",
            category=product_data.category or "Not specified",
            features=features_str,
            target_search_term=search_terms_display,
            search_terms_instruction=search_terms_instruction
        )
    
    def _parse_response(self, response: str, product_data: ProductData, target_search_terms: List[str], start_time: float) -> OptimizationResult:
        """Parse LLM response into OptimizationResult"""
        try:
            lines = response.strip().split('\n')
            
            # Initialize with defaults
            optimized_title = product_data.current_title
            confidence_score = 0.5
            reasoning = "Unable to parse response"
            keywords_used = []
            warnings = ["Failed to parse LLM response"]
            preservation_score = 0
            changes_made = []
            
            # Parse each line
            for line in lines:
                line = line.strip()
                if line.startswith('OPTIMIZED_TITLE:'):
                    optimized_title = line.replace('OPTIMIZED_TITLE:', '').strip()
                elif line.startswith('CONFIDENCE:'):
                    try:
                        confidence_score = float(line.replace('CONFIDENCE:', '').strip())
                    except ValueError:
                        confidence_score = 0.5
                elif line.startswith('REASONING:'):
                    reasoning = line.replace('REASONING:', '').strip()
                elif line.startswith('PRESERVATION_SCORE:'):
                    try:
                        preservation_score = float(line.replace('PRESERVATION_SCORE:', '').strip())
                    except ValueError:
                        preservation_score = 0
                elif line.startswith('KEYWORDS_USED:'):
                    keywords_str = line.replace('KEYWORDS_USED:', '').strip()
                    keywords_used = [kw.strip() for kw in keywords_str.split(',') if kw.strip()]
                elif line.startswith('CHANGES_MADE:'):
                    changes_str = line.replace('CHANGES_MADE:', '').strip()
                    changes_made = [c.strip() for c in changes_str.split(',') if c.strip()]
                elif line.startswith('WARNINGS:'):
                    warnings_str = line.replace('WARNINGS:', '').strip()
                    if warnings_str.lower() != 'none':
                        warnings = [w.strip() for w in warnings_str.split(',') if w.strip()]
                    else:
                        warnings = []
            
            processing_time = time.time() - start_time
            
            return OptimizationResult(
                original_title=product_data.current_title,
                optimized_title=optimized_title,
                target_search_term=", ".join(target_search_terms),  # Join multiple terms for display
                confidence_score=confidence_score,
                optimization_reasoning=reasoning,
                keywords_used=keywords_used,
                warnings=warnings,
                processing_time=processing_time,
                model_used=self.llm_client.model_name
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing LLM response: {e}")
            # Return a fallback result
            return OptimizationResult(
                original_title=product_data.current_title,
                optimized_title=product_data.current_title,
                target_search_term=", ".join(target_search_terms),  # Join multiple terms for display
                confidence_score=0.0,
                optimization_reasoning=f"Error parsing response: {str(e)}",
                keywords_used=[],
                warnings=[f"Parsing error: {str(e)}"],
                processing_time=time.time() - start_time,
                model_used=self.llm_client.model_name
            )
    
    def set_prompt_mode(self, mode: str = "preserve"):
        """Set the optimization prompt mode"""
        if mode == "preserve":
            # Use the default preserve prompt (already loaded)
            pass
        elif mode == "standard":
            # Switch to standard prompt
            self.optimization_prompt = self.standard_optimization_prompt
        else:
            raise ValueError(f"Unknown prompt mode: {mode}. Use 'preserve' or 'standard'")
    
    def get_optimizer_info(self) -> Dict[str, Any]:
        """Get information about the optimizer"""
        return {
            'llm_info': self.llm_client.get_model_info(),
            'prompt_loaded': bool(self.optimization_prompt),
            'current_prompt_mode': 'preserve' if 'PRESERVE FIRST' in self.optimization_prompt else 'standard'
        }
