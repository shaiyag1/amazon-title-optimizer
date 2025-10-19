# src/services/description_optimizer.py
"""
Description Optimizer for Amazon products
"""

import time
import logging
from typing import List, Dict, Any
from .data_models import ProductData, DescriptionOptimizationResult
from src.services.llm_client import LLMClient


class DescriptionOptimizer:
    """Optimizes product descriptions for better search term matching"""
    
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.logger = logging.getLogger(__name__)
        
        # Load prompt templates
        self._load_prompts()
    
    def _load_prompts(self):
        """Load description optimization prompt templates"""
        
        self.description_optimization_prompt = """
You are an expert Amazon product description optimizer specializing in creating compelling, SEO-optimized descriptions that perform well on Amazon.

PRODUCT INFORMATION:
- Product ID: {product_id}
- Brand: {brand}
- Product Type: {product_type}
- Current Description: {current_description}

{search_terms_instruction}

{intense_directive_section}

DESCRIPTION OPTIMIZATION PRINCIPLES:

1. CONTENT PRESERVATION REQUIREMENTS:
   - Maintain at least 75% of original description content
   - Keep all key specifications, benefits, and value propositions
   - Preserve the original tone and professional style
   - Maintain Amazon marketplace language standards
   - Never remove important technical details or measurements

2. SEARCH TERM INTEGRATION STRATEGY:
   - ADDITIVE APPROACH: Add search terms naturally to existing content
   - ENHANCEMENT APPROACH: Replace weak/generic words with specific search terms
   - INTEGRATION APPROACH: Weave search terms into existing phrases
   - NATURAL FLOW: Ensure search terms fit naturally and maintain readability

3. DESCRIPTION STRUCTURE OPTIMIZATION:
   - Opening sentence: Main product benefit or use case (incorporate primary search terms)
   - Middle sentences: Key features and advantages (integrate secondary search terms)
   - Closing: Call to action or key selling point (reinforce important search terms)
   - Length: Target 300-500 characters (concise but comprehensive)

4. AMAZON COMPLIANCE REQUIREMENTS:
   - Professional, engaging, benefit-focused tone
   - No false claims or misleading statements
   - Only include information supported by product data
   - Match Amazon's professional marketplace style
   - Avoid keyword stuffing - prioritize natural language

5. INTENSE DIRECTIVE HANDLING (if provided):
   - Follow the directive exactly as specified
   - Prioritize directive terms with maximum emphasis
   - Override preservation rules if necessary for directive compliance
   - Place directive terms in the most prominent positions
   - Use strong language and repetition when natural

OPTIMIZATION EXAMPLES:

GOOD DESCRIPTION OPTIMIZATION:
Original: "Experience superior lighting with our energy-efficient LED bulbs. Perfect for indoor and outdoor use, these long-lasting bulbs provide bright, natural daylight while reducing electricity costs."
Search Terms: "commercial grade LED lighting"
Optimized: "Experience superior COMMERCIAL GRADE LED LIGHTING with our energy-efficient LED bulbs. Perfect for indoor and outdoor use, these long-lasting COMMERCIAL GRADE bulbs provide bright, natural daylight while reducing electricity costs by up to 60%."
✅ Preserved 80%+ of original content while incorporating search terms naturally

BAD DESCRIPTION OPTIMIZATION:
Original: "Experience superior lighting with our energy-efficient LED bulbs. Perfect for indoor and outdoor use, these long-lasting bulbs provide bright, natural daylight while reducing electricity costs."
Search Terms: "commercial grade LED lighting"
Bad: "COMMERCIAL GRADE LED LIGHTING bulbs for commercial use. Energy efficient and long lasting."
❌ Removed too much valuable content and lost the original tone

RESPONSE FORMAT:
You MUST respond in this exact format:

OPTIMIZED_DESCRIPTION: [Your optimized description here - 300-500 characters recommended]
CONFIDENCE: [Score from 0.0 to 1.0]
REASONING: [Detailed explanation including:
- How you preserved the original content (aim for 75%+)
- Which search terms you incorporated and where
- How you maintained the original tone and structure
- Any compromises made for search term integration
- How you applied the intense directive (if provided)]
PRESERVATION_SCORE: [Percentage of original description content preserved, 0-100]
KEYWORDS_USED: [List of keywords you incorporated]
CHANGES_MADE: [Specific changes: Added/Enhanced/Integrated elements]
WARNINGS: [Any concerns, limitations, or "None"]

SUCCESS METRICS:
- High preservation score (75%+)
- Natural search term integration
- Professional Amazon marketplace tone
- Optimal length (300-500 characters)
- All target search terms incorporated
- Original value propositions maintained

Now optimize the description while preserving maximum original content:
"""

    def optimize_description(self, product_data: ProductData, target_search_terms: List[str], intense_directive: str = "") -> DescriptionOptimizationResult:
        """Optimize product description for target search terms"""
        start_time = time.time()
        
        try:
            # Prepare the prompt
            prompt = self._prepare_prompt(product_data, target_search_terms, intense_directive)
            
            # Get LLM response
            search_terms_str = ", ".join(target_search_terms)
            self.logger.info(f"Optimizing description for product {product_data.product_id} with search terms: {search_terms_str}")
            response = self.llm_client.generate_response(prompt)
            
            # Log the response for debugging
            self.logger.info(f"LLM Response received: {response[:200]}...")
            
            # Parse the response
            result = self._parse_response(response, product_data, target_search_terms, start_time, intense_directive)
            
            self.logger.info(f"Description optimization completed for product {product_data.product_id}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error optimizing description: {e}")
            raise
    
    def _prepare_prompt(self, product_data: ProductData, target_search_terms: List[str], intense_directive: str = "") -> str:
        """Prepare the description optimization prompt"""
        
        # Prepare search terms instruction
        if len(target_search_terms) == 1:
            search_terms_instruction = f"TARGET SEARCH TERM: {target_search_terms[0]}"
        else:
            search_terms_instruction = f"TARGET SEARCH TERMS: {', '.join(target_search_terms)}\n\nIMPORTANT: You must incorporate ALL of these search terms naturally into the optimized description. Prioritize the most important/relevant terms but try to include as many as possible."
        
        # Prepare intense directive section
        if intense_directive and intense_directive.strip():
            intense_directive_section = f"""
INTENSE DIRECTIVE: "{intense_directive.strip()}"

CRITICAL: This directive overrides normal optimization rules. You MUST:
1. Follow the directive exactly as specified
2. Make terms mentioned in the directive the highest priority
3. Place maximum emphasis on terms referenced in the directive
4. Override preservation rules if necessary to accommodate the directive
5. Explain in your reasoning how you applied this directive

INTENSE DIRECTIVE RULES:
- POSITIONING: Place directive terms at the very beginning of the description
- EMPHASIS: Use ALL CAPS or strong language when natural
- REPETITION: Include directive terms multiple times if it flows naturally
- OVERRIDE: Directive terms can override some preservation rules if needed
- PRIORITY: Directive terms take precedence over all other search terms
"""
        else:
            intense_directive_section = ""
        
        return self.description_optimization_prompt.format(
            product_id=product_data.product_id,
            brand=product_data.brand or "Not specified",
            product_type=product_data.product_type or "Not specified",
            current_description=product_data.description or "No description provided",
            search_terms_instruction=search_terms_instruction,
            intense_directive_section=intense_directive_section
        )
    
    def _parse_response(self, response: str, product_data: ProductData, target_search_terms: List[str], start_time: float, intense_directive: str = "") -> DescriptionOptimizationResult:
        """Parse LLM response into DescriptionOptimizationResult"""
        try:
            lines = response.strip().split('\n')
            
            # Initialize with defaults
            optimized_description = product_data.description or "No description provided"
            confidence_score = 0.5
            reasoning = "Description optimization completed"
            keywords_used = target_search_terms.copy()
            warnings = []
            preservation_score = 75.0
            
            # Parse response lines
            for line in lines:
                line = line.strip()
                if line.startswith("OPTIMIZED_DESCRIPTION:"):
                    optimized_description = line.replace("OPTIMIZED_DESCRIPTION:", "").strip()
                elif line.startswith("CONFIDENCE:"):
                    try:
                        confidence_score = float(line.replace("CONFIDENCE:", "").strip())
                    except ValueError:
                        confidence_score = 0.5
                elif line.startswith("REASONING:"):
                    reasoning = line.replace("REASONING:", "").strip()
                elif line.startswith("PRESERVATION_SCORE:"):
                    try:
                        preservation_score = float(line.replace("PRESERVATION_SCORE:", "").strip().replace("%", ""))
                    except ValueError:
                        preservation_score = 75.0
                elif line.startswith("KEYWORDS_USED:"):
                    keywords_str = line.replace("KEYWORDS_USED:", "").strip()
                    if keywords_str:
                        keywords_used = [kw.strip() for kw in keywords_str.split(",") if kw.strip()]
                elif line.startswith("CHANGES_MADE:"):
                    # Store changes for potential future use
                    pass
                elif line.startswith("WARNINGS:"):
                    warning_text = line.replace("WARNINGS:", "").strip()
                    if warning_text and warning_text.lower() != "none":
                        warnings.append(warning_text)
            
            # Calculate preservation score if not provided
            if preservation_score == 75.0 and product_data.description:
                # Simple word-based preservation calculation
                original_words = set(product_data.description.lower().split())
                optimized_words = set(optimized_description.lower().split())
                if original_words:
                    preserved_words = len(original_words.intersection(optimized_words))
                    preservation_score = (preserved_words / len(original_words)) * 100
            
            processing_time = time.time() - start_time
            
            # Check if intense directive was applied by looking for directive-related keywords in reasoning
            intense_directive_applied = False
            if intense_directive and intense_directive.strip():
                directive_keywords = ['directive', 'intense', 'priority', 'emphasized', 'prominent', 'front-loaded']
                reasoning_lower = reasoning.lower()
                intense_directive_applied = any(keyword in reasoning_lower for keyword in directive_keywords)
            
            return DescriptionOptimizationResult(
                original_description=product_data.description or "No description provided",
                optimized_description=optimized_description,
                target_search_terms=target_search_terms,
                confidence_score=confidence_score,
                optimization_reasoning=reasoning,
                keywords_used=keywords_used,
                warnings=warnings,
                processing_time=processing_time,
                model_used=self.llm_client.model_name,
                intense_directive=intense_directive if intense_directive and intense_directive.strip() else None,
                intense_directive_applied=intense_directive_applied,
                preservation_score=preservation_score
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing LLM response: {e}")
            # Return a fallback result
            return DescriptionOptimizationResult(
                original_description=product_data.description or "No description provided",
                optimized_description=product_data.description or "No description provided",
                target_search_terms=target_search_terms,
                confidence_score=0.0,
                optimization_reasoning=f"Error parsing response: {str(e)}",
                keywords_used=[],
                warnings=[f"Parsing error: {str(e)}"],
                processing_time=time.time() - start_time,
                model_used=self.llm_client.model_name,
                intense_directive=intense_directive if intense_directive and intense_directive.strip() else None,
                intense_directive_applied=False,
                preservation_score=0.0
            )
