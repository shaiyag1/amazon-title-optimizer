# src/services/content_optimizer.py
"""
Content Optimizer for Amazon products - optimizes title, features, and description
"""

import time
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from .llm_client import LLMClient
from .data_models import ProductData


@dataclass
class ContentOptimizationResult:
    """Result of content optimization across title, features, and description"""
    # Original content
    original_title: str
    original_features: str
    original_description: str
    
    # Optimized content
    optimized_title: str
    optimized_features: str
    optimized_description: str
    
    # Metadata
    search_terms: List[Dict[str, Any]]  # [{"term": "...", "priority": 1}]
    element_order: List[str]
    confidence_score: float
    reasoning: str
    keywords_placement: Dict[str, List[str]]  # Which keywords went where
    warnings: List[str]
    processing_time: float
    model_used: str


class ContentOptimizer:
    """Optimizes all Amazon product content (title, features, description) with priority-based search term placement"""
    
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.logger = logging.getLogger(__name__)
        self._load_prompts()
    
    def _load_prompts(self):
        """Load optimization prompt templates"""
        
        self.content_optimization_prompt = """
You are an expert Amazon content optimizer specializing in COMPREHENSIVE product optimization across title, features, and description.

Your mission is to optimize ALL THREE content elements (title, features, description) while:
1. Incorporating search terms based on their priority and element importance
2. Preserving 90%+ of original content in each element
3. Maintaining Amazon compliance and natural language

PRODUCT INFORMATION:
- Product ID: {product_id}
- Brand: {brand}
- Product Type: {product_type}

CURRENT CONTENT:
=== TITLE ===
{current_title}

=== FEATURES ===
{current_features}

=== DESCRIPTION ===
{current_description}

SEARCH TERMS WITH PRIORITIES:
{search_terms_info}

ELEMENT IMPORTANCE ORDER (Most Important → Least Important):
{element_order}

{description_generation_instruction}

OPTIMIZATION STRATEGY:

1. PRIORITY SYSTEM RULES:
   - Priority 2 (HIGH): These terms MUST go into the MOST IMPORTANT element (based on element order above)
     * Place at the beginning when natural
     * Make them prominent and noticeable
     * If multiple priority 2 terms exist, distribute them thoughtfully within the most important element
   
   - Priority 1 (STANDARD): These terms should be placed based on best natural fit
     * Distribute across all three elements as appropriate
     * Focus on natural integration
     * Don't force placement
   
   - If ALL terms have the same priority: Ignore priority, use natural fit for all terms

2. ELEMENT-SPECIFIC OPTIMIZATION:
   
   TITLE OPTIMIZATION:
   - Amazon character limit: 200 characters
   - Most important for search ranking (if in element order)
   - Keep 90%+ of original content
   - Front-load priority 2 terms when this is the most important element
   - Maintain brand name and key specifications
   
   FEATURES OPTIMIZATION:
   - 5 bullet points recommended
   - Each bullet should start with a benefit/feature
   - Integrate search terms naturally into existing features
   - Can add ONE new feature if needed for search terms
   - Keep professional, scannable format
   
   DESCRIPTION OPTIMIZATION:
   - 2000 character limit (be concise, ~300-500 chars recommended)
   - Tell the product story
   - Integrate search terms naturally
   - Can be more narrative and descriptive
   - Support claims made in title and features

3. CONTENT PRESERVATION REQUIREMENTS:
   - Maintain 90%+ of original content in EACH element
   - Never remove specifications, quantities, or technical details
   - Keep all existing value propositions
   - Preserve brand voice and tone
   - Only remove truly redundant words

4. SEARCH TERM INTEGRATION:
   - ADDITIVE: Add search terms to existing content
   - ENHANCEMENT: Replace weak words with search terms
   - INTEGRATION: Weave search terms into existing phrases
   - NATURAL FIT: Prioritize readability over keyword stuffing

5. CROSS-ELEMENT COORDINATION:
   - Ensure consistency across all three elements
   - Don't repeat the exact same phrases across elements
   - Each element should complement the others
   - Maintain coherent product narrative

RESPONSE FORMAT:
You MUST respond in this exact format:

OPTIMIZED_TITLE: [Your optimized title here - under 200 chars]

OPTIMIZED_FEATURES: [Your optimized features here - maintain bullet format if original had bullets]

OPTIMIZED_DESCRIPTION: [Your optimized description here - 300-500 chars recommended]

CONFIDENCE: [Score from 0.0 to 1.0]

REASONING: [Detailed explanation including:
- Which priority 2 terms went where and why
- Which priority 1 terms went where and why
- How you balanced element importance order with natural fit
- Any challenges or compromises made
- Why certain terms were placed in specific elements]

KEYWORDS_PLACEMENT: [Format: "title: term1, term2 | features: term3, term4 | description: term5, term6"]

WARNINGS: [Any concerns, compromises, or limitations - or "None"]

CRITICAL REMINDERS:
- Priority 2 terms MUST be prominent in the most important element ({most_important_element})
- Preserve 90%+ content in ALL three elements
- Maintain Amazon compliance (no false claims, stay within character limits)
- Natural language is essential - avoid keyword stuffing
- Explain your reasoning clearly, especially priority term placement

Now optimize all three content elements:
"""

        self.description_generation_prompt = """
You are an expert Amazon product content writer specializing in creating compelling, professional product descriptions.

PRODUCT INFORMATION:
- Product ID: {product_id}
- Brand: {brand}
- Product Type: {product_type}

EXISTING CONTENT:
=== TITLE ===
{current_title}

=== FEATURES ===
{current_features}

TASK: Generate a professional Amazon product description (~300 characters)

DESCRIPTION REQUIREMENTS:
1. LENGTH: Approximately 300 characters (concise but comprehensive)
2. STYLE: Professional, engaging, benefit-focused
3. CONTENT: Based on the title and features provided
4. TONE: Match Amazon's professional marketplace style
5. ACCURACY: Only include information supported by title/features
6. NO FALSE CLAIMS: Never invent features or specifications

DESCRIPTION STRUCTURE:
- Opening sentence: Main product benefit or use case
- Middle sentences: Key features and advantages
- Closing: Call to action or key selling point

EXAMPLES OF GOOD DESCRIPTIONS:
"Experience superior lighting with our energy-efficient LED bulbs. Perfect for indoor and outdoor use, these long-lasting bulbs provide bright, natural daylight while reducing electricity costs by up to 60%. Easy to install and backed by our quality guarantee."

RESPONSE FORMAT:
GENERATED_DESCRIPTION: [Your 300-character product description here]

REASONING: [Brief explanation of your approach]

Now generate the product description:
"""
    
    def optimize_content(
        self,
        current_title: str,
        current_features: str,
        current_description: str,
        search_terms: List[Dict[str, Any]],  # [{"term": "outdoor lighting", "priority": 2}, ...]
        element_order: List[str] = ["title", "features", "description"],
        product_data: Optional[ProductData] = None
    ) -> ContentOptimizationResult:
        """
        Optimize all content elements (title, features, description) with priority-based search term placement
        
        Args:
            current_title: Current product title
            current_features: Current product features (string format)
            current_description: Current product description (or "Generate Description" to auto-generate)
            search_terms: List of dicts with "term" and "priority" (1 or 2)
            element_order: Order of importance ["title", "features", "description"]
            product_data: Optional additional product context
        
        Returns:
            ContentOptimizationResult with optimized content
        """
        start_time = time.time()
        
        try:
            # Check if we need to generate description first
            needs_description_generation = (
                not current_description or 
                current_description.strip().lower() == "generate description"
            )
            
            if needs_description_generation:
                self.logger.info("Generating description before optimization")
                current_description = self._generate_description(
                    current_title, current_features, product_data
                )
            
            # Validate element order
            valid_elements = {"title", "features", "description"}
            if not all(elem in valid_elements for elem in element_order):
                raise ValueError(f"Invalid element in element_order. Must be from: {valid_elements}")
            
            # Check if all priorities are the same (priority becomes meaningless)
            priorities = [st.get("priority", 1) for st in search_terms]
            all_same_priority = len(set(priorities)) == 1
            
            if all_same_priority:
                self.logger.info("All search terms have same priority - using natural fit strategy")
            
            # Prepare and execute optimization
            prompt = self._prepare_content_prompt(
                current_title, current_features, current_description,
                search_terms, element_order, product_data, all_same_priority
            )
            
            self.logger.info(f"Optimizing content with {len(search_terms)} search terms")
            response = self.llm_client.generate_response(prompt)
            
            # Parse response
            result = self._parse_content_response(
                response, current_title, current_features, current_description,
                search_terms, element_order, start_time
            )
            
            self.logger.info("Content optimization completed successfully")
            return result
            
        except Exception as e:
            self.logger.error(f"Error optimizing content: {e}")
            raise
    
    def _generate_description(
        self,
        current_title: str,
        current_features: str,
        product_data: Optional[ProductData] = None
    ) -> str:
        """Generate a product description based on title and features"""
        try:
            prompt = self.description_generation_prompt.format(
                product_id=product_data.product_id if product_data else "Unknown",
                brand=product_data.brand if product_data else "Not specified",
                product_type=product_data.product_type if product_data else "Not specified",
                current_title=current_title,
                current_features=current_features
            )
            
            self.logger.info("Calling LLM to generate description")
            response = self.llm_client.generate_response(prompt)
            
            # Parse the generated description
            for line in response.strip().split('\n'):
                if 'GENERATED_DESCRIPTION:' in line:
                    description = line.split(':', 1)[1].strip()
                    self.logger.info(f"Generated description: {description[:100]}...")
                    return description
            
            # Fallback if parsing fails
            self.logger.warning("Could not parse generated description, using response directly")
            return response.strip()[:300]
            
        except Exception as e:
            self.logger.error(f"Error generating description: {e}")
            return "Premium quality product designed for superior performance and reliability."
    
    def _prepare_content_prompt(
        self,
        current_title: str,
        current_features: str,
        current_description: str,
        search_terms: List[Dict],
        element_order: List[str],
        product_data: Optional[ProductData],
        all_same_priority: bool
    ) -> str:
        """Prepare the comprehensive content optimization prompt"""
        
        # Format search terms info
        search_terms_lines = []
        for i, st in enumerate(search_terms, 1):
            term = st.get("term", "")
            priority = st.get("priority", 1)
            priority_label = "HIGH PRIORITY" if priority == 2 else "STANDARD"
            search_terms_lines.append(f"{i}. \"{term}\" - Priority {priority} ({priority_label})")
        
        if all_same_priority:
            search_terms_lines.append("\nNOTE: All terms have same priority - use natural fit strategy for all terms")
        
        search_terms_info = "\n".join(search_terms_lines)
        
        # Format element order
        element_order_str = " → ".join([f"{i+1}. {elem.upper()}" for i, elem in enumerate(element_order)])
        most_important_element = element_order[0].upper()
        
        # Check if description generation is needed
        description_instruction = ""
        if not current_description or len(current_description.strip()) < 20:
            description_instruction = "\nNOTE: The current description is minimal or empty. You may need to create more substantial description content."
        
        return self.content_optimization_prompt.format(
            product_id=product_data.product_id if product_data else "Unknown",
            brand=product_data.brand if product_data else "Not specified",
            product_type=product_data.product_type if product_data else "Not specified",
            current_title=current_title,
            current_features=current_features,
            current_description=current_description or "[Empty - needs content]",
            search_terms_info=search_terms_info,
            element_order=element_order_str,
            most_important_element=most_important_element,
            description_generation_instruction=description_instruction
        )
    
    def _parse_content_response(
        self,
        response: str,
        original_title: str,
        original_features: str,
        original_description: str,
        search_terms: List[Dict],
        element_order: List[str],
        start_time: float
    ) -> ContentOptimizationResult:
        """Parse LLM response into ContentOptimizationResult"""
        
        try:
            lines = response.strip().split('\n')
            
            # Initialize defaults
            optimized_title = original_title
            optimized_features = original_features
            optimized_description = original_description
            confidence_score = 0.5
            reasoning = "Unable to parse response"
            keywords_placement = {}
            warnings = []
            
            # Parse multi-line fields
            current_field = None
            field_content = []
            
            for line in lines:
                line_upper = line.strip().upper()
                
                if 'OPTIMIZED_TITLE:' in line_upper:
                    if current_field and field_content:
                        self._save_field(current_field, field_content, locals())
                    current_field = 'title'
                    field_content = [line.split(':', 1)[1].strip()]
                    
                elif 'OPTIMIZED_FEATURES:' in line_upper:
                    if current_field and field_content:
                        self._save_field(current_field, field_content, locals())
                    current_field = 'features'
                    field_content = [line.split(':', 1)[1].strip()]
                    
                elif 'OPTIMIZED_DESCRIPTION:' in line_upper:
                    if current_field and field_content:
                        self._save_field(current_field, field_content, locals())
                    current_field = 'description'
                    field_content = [line.split(':', 1)[1].strip()]
                    
                elif 'CONFIDENCE:' in line_upper:
                    if current_field and field_content:
                        self._save_field(current_field, field_content, locals())
                    try:
                        confidence_score = float(line.split(':', 1)[1].strip())
                    except:
                        confidence_score = 0.5
                    current_field = None
                    field_content = []
                    
                elif 'REASONING:' in line_upper:
                    if current_field and field_content:
                        self._save_field(current_field, field_content, locals())
                    current_field = 'reasoning'
                    field_content = [line.split(':', 1)[1].strip()]
                    
                elif 'KEYWORDS_PLACEMENT:' in line_upper:
                    if current_field and field_content:
                        self._save_field(current_field, field_content, locals())
                    # Parse keywords placement
                    placement_str = line.split(':', 1)[1].strip()
                    keywords_placement = self._parse_keywords_placement(placement_str)
                    current_field = None
                    field_content = []
                    
                elif 'WARNINGS:' in line_upper:
                    if current_field and field_content:
                        self._save_field(current_field, field_content, locals())
                    warnings_str = line.split(':', 1)[1].strip()
                    if warnings_str.lower() not in ['none', 'n/a']:
                        warnings = [w.strip() for w in warnings_str.split(',')]
                    current_field = None
                    field_content = []
                    
                elif current_field and line.strip():
                    # Continue multi-line field
                    field_content.append(line.strip())
            
            # Save last field
            if current_field and field_content:
                content = ' '.join(field_content).strip()
                if current_field == 'title':
                    optimized_title = content
                elif current_field == 'features':
                    optimized_features = content
                elif current_field == 'description':
                    optimized_description = content
                elif current_field == 'reasoning':
                    reasoning = content
            
            processing_time = time.time() - start_time
            
            return ContentOptimizationResult(
                original_title=original_title,
                original_features=original_features,
                original_description=original_description,
                optimized_title=optimized_title,
                optimized_features=optimized_features,
                optimized_description=optimized_description,
                search_terms=search_terms,
                element_order=element_order,
                confidence_score=confidence_score,
                reasoning=reasoning,
                keywords_placement=keywords_placement,
                warnings=warnings,
                processing_time=processing_time,
                model_used=self.llm_client.model_name
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing content response: {e}")
            # Return fallback result
            return ContentOptimizationResult(
                original_title=original_title,
                original_features=original_features,
                original_description=original_description,
                optimized_title=original_title,
                optimized_features=original_features,
                optimized_description=original_description,
                search_terms=search_terms,
                element_order=element_order,
                confidence_score=0.0,
                reasoning=f"Error parsing response: {str(e)}",
                keywords_placement={},
                warnings=[f"Parsing error: {str(e)}"],
                processing_time=time.time() - start_time,
                model_used=self.llm_client.model_name
            )
    
    def _save_field(self, field_name: str, content_lines: List[str], local_vars: dict):
        """Helper to save parsed field content"""
        content = ' '.join(content_lines).strip()
        if field_name == 'title':
            local_vars['optimized_title'] = content
        elif field_name == 'features':
            local_vars['optimized_features'] = content
        elif field_name == 'description':
            local_vars['optimized_description'] = content
        elif field_name == 'reasoning':
            local_vars['reasoning'] = content
    
    def _parse_keywords_placement(self, placement_str: str) -> Dict[str, List[str]]:
        """Parse keywords placement string into dictionary"""
        try:
            result = {}
            parts = placement_str.split('|')
            for part in parts:
                if ':' in part:
                    element, terms = part.split(':', 1)
                    element = element.strip().lower()
                    terms_list = [t.strip() for t in terms.split(',')]
                    result[element] = terms_list
            return result
        except:
            return {}
    
    def set_prompt_mode(self, mode: str = "preserve"):
        """Set the optimization prompt mode"""
        # ContentOptimizer uses preserve mode by default
        # This method is here for compatibility with TitleOptimizer interface
        if mode == "preserve":
            # Default mode - already using preserve strategy
            pass
        elif mode == "standard":
            # Could add a more aggressive prompt in the future
            self.logger.info("ContentOptimizer currently only supports preserve mode")
        else:
            raise ValueError(f"Unknown prompt mode: {mode}. Use 'preserve' or 'standard'")
    
    def get_optimizer_info(self) -> Dict[str, Any]:
        """Get information about the optimizer"""
        return {
            'llm_info': self.llm_client.get_model_info(),
            'prompt_loaded': bool(self.content_optimization_prompt),
            'current_prompt_mode': 'preserve'
        }