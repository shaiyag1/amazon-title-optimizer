# src/services/bullets_optimizer.py
"""
Amazon Product Bullets Optimizer - Optimizes product bullet points with priority-based search term promotion
"""

import time
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from .llm_client import LLMClient
from .data_models import ProductData


@dataclass
class BulletsOptimizationResult:
    """Result of product bullets optimization"""
    # Original and optimized content
    original_bullets: List[str]
    optimized_bullets: List[str]
    
    # Search terms used
    standard_search_terms: List[str]
    high_priority_search_terms: List[str]
    
    # Metadata
    confidence_score: float
    optimization_reasoning: str
    keywords_used: List[str]
    changes_made: List[str]
    preservation_score: float
    warnings: List[str]
    processing_time: float
    model_used: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for display"""
        return {
            'original_bullets': self.original_bullets,
            'optimized_bullets': self.optimized_bullets,
            'standard_search_terms': self.standard_search_terms,
            'high_priority_search_terms': self.high_priority_search_terms,
            'confidence_score': self.confidence_score,
            'optimization_reasoning': self.optimization_reasoning,
            'keywords_used': self.keywords_used,
            'changes_made': self.changes_made,
            'preservation_score': self.preservation_score,
            'warnings': self.warnings,
            'processing_time': self.processing_time,
            'model_used': self.model_used
        }


class AmazonProductBulletsOptimizer:
    """Optimizes Amazon product bullet points with priority-based search term promotion"""
    
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.logger = logging.getLogger(__name__)
        
        # Load prompt templates
        self._load_prompts()
    
    def _load_prompts(self):
        """Load optimization prompt templates"""
        
        self.bullets_optimization_prompt = """
You are an expert Amazon product bullets optimizer. Your mission is to optimize product bullet points (features) by incorporating search terms with SPECIAL ATTENTION to high-priority promotional terms.

PRODUCT INFORMATION:
- Product ID: {product_id}
- Brand: {brand}
- Product Type: {product_type}
- Description: {description}
- Category: {category}

CURRENT BULLETS:
{current_bullets}

SEARCH TERMS TO INCORPORATE:
{search_terms_info}

{high_priority_directive}

OPTIMIZATION STRATEGY:

1. PRIORITY-BASED PROMOTION SYSTEM:
   
   HIGH PRIORITY SEARCH TERMS ({high_priority_count} total):
   - These terms deserve EXTRA EMPHASIS and prominent placement
   - Try to place them in MULTIPLE bullets when natural
   - Use STRONG, BENEFIT-FOCUSED language around these terms
   - Consider starting bullets with these terms for maximum visibility
   - Example: "ENERGY-EFFICIENT LED TECHNOLOGY delivers..."
   
   STANDARD SEARCH TERMS ({standard_count} total):
   - Integrate these naturally across bullets
   - Don't sacrifice readability for keyword stuffing
   - Balance with high-priority terms appropriately

2. BULLETS OPTIMIZATION RULES:

   PRESERVATION REQUIREMENTS:
   - Keep 80%+ of original bullet content
   - Maintain all key specifications, quantities, and benefits
   - Preserve the professional tone and format
   - Keep technical details and measurements intact
   - Don't remove valuable information to make room for search terms

   INTEGRATION STRATEGIES:
   
   STRATEGY A - REFINE EXISTING BULLETS:
   - Modify existing bullets to incorporate search terms
   - Add search terms naturally to current phrases
   - Replace weak/generic words with search terms
   - Example: "High-quality materials" → "PROFESSIONAL-GRADE HIGH-QUALITY materials"
   
   STRATEGY B - ADD NEW BULLETS:
   - Add 1-2 new bullets that feature high-priority search terms
   - These bullets should complement existing ones
   - Focus on benefits and features not already covered
   - Keep total bullets to 5-7 for best Amazon performance
   
   STRATEGY C - COMBINED APPROACH:
   - Use both refined existing bullets AND new bullets
   - High-priority terms can appear in both existing and new bullets
   - Ensure comprehensive coverage without redundancy

3. HIGH-PRIORITY TERM PROMOTION TECHNIQUES:

   TECHNIQUE 1 - POSITION PROMINENTLY:
   - Place high-priority terms at the beginning of bullets when possible
   - Front-load the most important promotional terms
   
   TECHNIQUE 2 - REPEAT NATURALLY:
   - Incorporate high-priority terms into 2-3 bullets if relevant
   - Natural variation: "ENERGY EFFICIENT", "Energy efficiency", "energy-efficient"
   
   TECHNIQUE 3 - EMPHASIZE BENEFITS:
   - Frame high-priority terms with strong benefit language
   - Example: "REVOLUTIONARY CLEANING TECHNOLOGY ensures..."
   
   TECHNIQUE 4 - PRIORITIZE VISIBILITY:
   - High-priority terms should be MORE VISIBLE than standard terms
   - Use stronger adjectives and more compelling phrasing

4. CONTENT GUIDELINES:

   BULLETS BEST PRACTICES:
   - Each bullet should start with a benefit or feature
   - Keep bullets concise (ideally 1-2 lines each)
   - Use ALL CAPS for emphasis sparingly (1-2 words max)
   - Maintain scannable, professional format
   - Focus on customer benefits and product advantages
   
   AMAZON COMPLIANCE:
   - No false claims or misleading statements
   - Only include information about real product features
   - Maintain professional marketplace tone
   - Avoid over-promising or deceptive language

5. DECISION MAKING:

   ANALYZE EXISTING BULLETS:
   - Review current bullets to identify where search terms fit naturally
   - Identify gaps where new bullets would add value
   - Assess if high-priority terms need special emphasis
   
   STRATEGIC PLACEMENT:
   - Which strategy (A, B, or C) makes most sense?
   - Where do high-priority terms naturally fit?
   - How can you maximize search term coverage?
   - Can you maintain 80%+ content preservation?

OPTIMIZATION EXAMPLES:

GOOD BULLETS OPTIMIZATION:
Original Bullets:
1. "Durable construction for long-lasting use"
2. "Easy to install and maintain"
3. "Suitable for indoor applications"

Search Terms: Standard: ["cleaning solution"], High Priority: ["commercial grade", "professional quality"]

Optimized Bullets:
1. "COMMERCIAL-GRADE durable construction ensures long-lasting professional quality performance"
2. "Easy to install and maintain - perfect for commercial-grade cleaning solutions"
3. "PROFESSIONAL QUALITY materials suitable for indoor applications"
4. "Advanced commercial-grade cleaning solution technology"

✅ High-priority terms prominently placed, natural integration, preserved content

BAD BULLETS OPTIMIZATION:
Original: "Durable construction for long-lasting use"
High Priority: "commercial grade"
Bad: "COMMERCIAL GRADE COMMERCIAL GRADE durable commercial grade construction"
❌ Over-stuffing keywords, unnatural language, poor readability

RESPONSE FORMAT:
You MUST respond in this exact format:

OPTIMIZED_BULLETS: [List your optimized bullets here, one per line, numbered]
1. [First bullet]
2. [Second bullet]
3. [Third bullet]
...

CONFIDENCE: [Score from 0.0 to 1.0]

REASONING: [Detailed explanation including:
- Which strategy you chose (A, B, or C) and why
- How you promoted high-priority terms vs standard terms
- Which bullets you refined vs added
- How you maintained content preservation (target 80%+)
- Any specific promotion techniques you used]

PRESERVATION_SCORE: [Percentage of original content preserved, 0-100]

KEYWORDS_USED: [List of all keywords you incorporated, separated by commas]

CHANGES_MADE: [List of specific changes: "Bullet 1: added X", "Added new bullet: Y", etc.]

WARNINGS: [Any concerns, limitations, or "None"]

SUCCESS CRITERIA:
- 80%+ content preservation
- All high-priority terms prominently placed
- Natural, readable bullets
- Professional Amazon format
- Comprehensive search term coverage
- Maximum 7 bullets total

Now optimize the bullets with priority-based search term promotion:
"""

    def optimize_bullets(
        self,
        product_data: ProductData,
        standard_search_terms: List[str],
        high_priority_search_terms: List[str] = None,
        add_new_bullets: bool = True
    ) -> BulletsOptimizationResult:
        """
        Optimize product bullets with priority-based search term promotion
        
        Args:
            product_data: Product information including current bullets
            standard_search_terms: Regular search terms to incorporate
            high_priority_search_terms: Terms that should be highly promoted
            add_new_bullets: Whether to allow adding new bullets
            
        Returns:
            BulletsOptimizationResult with optimized bullets
        """
        start_time = time.time()
        
        try:
            # Validate input
            if not product_data.features:
                raise ValueError("Product data must include features/bullets")
            
            # Convert features to list if needed
            if isinstance(product_data.features, str):
                original_bullets = [b.strip() for b in product_data.features.split('\n') if b.strip()]
            else:
                original_bullets = [f.strip() for f in product_data.features if f and f.strip()]
            
            if not original_bullets:
                raise ValueError("No bullets found in product data")
            
            # Set default for high priority terms
            if high_priority_search_terms is None:
                high_priority_search_terms = []
            
            # Prepare the prompt
            prompt = self._prepare_prompt(
                product_data, 
                original_bullets,
                standard_search_terms, 
                high_priority_search_terms,
                add_new_bullets
            )
            
            # Log the optimization attempt
            self.logger.info(
                f"Optimizing bullets for product {product_data.product_id} with "
                f"{len(standard_search_terms)} standard terms and "
                f"{len(high_priority_search_terms)} high-priority terms"
            )
            
            # Get LLM response
            response = self.llm_client.generate_response(prompt)
            self.logger.info(f"LLM Response received: {response[:200]}...")
            
            # Parse the response
            result = self._parse_response(
                response, 
                original_bullets,
                standard_search_terms,
                high_priority_search_terms,
                start_time
            )
            
            self.logger.info(f"Bullets optimization completed for product {product_data.product_id}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error optimizing bullets: {e}")
            raise
    
    def _prepare_prompt(
        self,
        product_data: ProductData,
        current_bullets: List[str],
        standard_search_terms: List[str],
        high_priority_search_terms: List[str],
        add_new_bullets: bool
    ) -> str:
        """Prepare the bullets optimization prompt"""
        
        # Format current bullets
        bullets_str = "\n".join([f"{i+1}. {bullet}" for i, bullet in enumerate(current_bullets)])
        
        # Format search terms info
        search_terms_lines = []
        
        if high_priority_search_terms:
            search_terms_lines.append("HIGH PRIORITY SEARCH TERMS (Promote These):")
            for i, term in enumerate(high_priority_search_terms, 1):
                search_terms_lines.append(f"  HIGH {i}. \"{term}\"")
            search_terms_lines.append("")
        
        if standard_search_terms:
            search_terms_lines.append("STANDARD SEARCH TERMS:")
            for i, term in enumerate(standard_search_terms, 1):
                search_terms_lines.append(f"  STD {i}. \"{term}\"")
        
        if not search_terms_lines:
            search_terms_lines.append("No specific search terms provided")
        
        search_terms_info = "\n".join(search_terms_lines)
        
        # Create high-priority directive
        high_priority_directive = ""
        if high_priority_search_terms:
            terms_str = ", ".join([f'"{term}"' for term in high_priority_search_terms])
            high_priority_directive = f"""
CRITICAL HIGH-PRIORITY PROMOTION DIRECTIVE:
You have {len(high_priority_search_terms)} HIGH-PRIORITY search term(s) that MUST be heavily promoted:
{', '.join([f'"{term}"' for term in high_priority_search_terms])}

These terms should:
- Appear in MULTIPLE bullets when natural and relevant
- Be placed at the BEGINNING of bullets whenever possible
- Use STRONG language and emphasis
- Be MORE VISIBLE than standard search terms
- Frame in compelling benefit statements

Compare this to the {len(standard_search_terms)} standard search terms which should be integrated naturally but don't need special emphasis.
"""
        
        # Format add_new_bullets instruction
        new_bullets_note = ""
        if add_new_bullets:
            new_bullets_note = "You ARE allowed to add new bullets (up to 2) if they enhance search term coverage."
        else:
            new_bullets_note = "You should ONLY refine existing bullets. DO NOT add new bullets."
        
        return self.bullets_optimization_prompt.format(
            product_id=product_data.product_id,
            brand=product_data.brand or "Not specified",
            product_type=product_data.product_type or "Not specified",
            description=product_data.description or "Not provided",
            category=product_data.category or "Not specified",
            current_bullets=bullets_str,
            search_terms_info=search_terms_info,
            high_priority_directive=high_priority_directive,
            high_priority_count=len(high_priority_search_terms),
            standard_count=len(standard_search_terms),
            add_new_bullets_note=new_bullets_note
        )
    
    def _parse_response(
        self,
        response: str,
        original_bullets: List[str],
        standard_search_terms: List[str],
        high_priority_search_terms: List[str],
        start_time: float
    ) -> BulletsOptimizationResult:
        """Parse LLM response into BulletsOptimizationResult"""
        
        try:
            lines = response.strip().split('\n')
            
            # Initialize defaults
            optimized_bullets = original_bullets.copy()
            confidence_score = 0.5
            reasoning = "Unable to parse response"
            keywords_used = []
            changes_made = []
            preservation_score = 0
            warnings = []
            
            # Parse each field
            i = 0
            field_keywords = ['OPTIMIZED_BULLETS', 'CONFIDENCE', 'REASONING', 'PRESERVATION_SCORE',
                            'KEYWORDS_USED', 'CHANGES_MADE', 'WARNINGS']
            
            in_bullets_section = False
            bullets_list = []
            
            while i < len(lines):
                line = lines[i].strip()
                
                if 'OPTIMIZED_BULLETS' in line and ':' in line:
                    # Start capturing bullets
                    in_bullets_section = True
                    i += 1
                    
                    # Continue capturing bullets until we hit the next field
                    while i < len(lines):
                        next_line = lines[i].strip()
                        
                        # Check if this is the start of a new field
                        if next_line and any(field + ':' in next_line.upper() for field in field_keywords):
                            in_bullets_section = False
                            break
                        
                        # Check if this looks like a bullet point (starts with number or dash)
                        if (next_line and 
                            (next_line[0].isdigit() or next_line.startswith('-') or next_line.startswith('•')) and
                            len(next_line) > 10):
                            # Extract the bullet text (remove numbering)
                            bullet_text = next_line
                            # Remove leading number/dash/bullet
                            while bullet_text and (bullet_text[0].isdigit() or bullet_text[0] in '-•. '):
                                bullet_text = bullet_text[1:].lstrip()
                            if bullet_text:
                                bullets_list.append(bullet_text)
                        
                        i += 1
                    
                    optimized_bullets = bullets_list if bullets_list else original_bullets
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
                    reasoning = ' '.join(reasoning_parts).strip()
                    continue
                
                elif 'PRESERVATION_SCORE' in line and ':' in line:
                    try:
                        preservation_score = float(line.split(':', 1)[1].strip())
                    except ValueError:
                        preservation_score = 0
                    i += 1
                
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
                
                elif 'CHANGES_MADE' in line and ':' in line:
                    # Capture multi-line changes
                    changes_parts = [line.split(':', 1)[1].strip()]
                    i += 1
                    while i < len(lines):
                        next_line = lines[i].strip()
                        if next_line and any(field + ':' in next_line.upper() for field in field_keywords):
                            break
                        if next_line:
                            changes_parts.append(next_line)
                        i += 1
                    changes_str = ' '.join(changes_parts).strip()
                    changes_made = [c.strip() for c in changes_str.split(',') if c.strip()]
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
            
            # If no bullets were parsed but we got a response, try to extract any numbered list
            if optimized_bullets == original_bullets and len(response.strip()) > 50:
                fallback_bullets = []
                for line in lines:
                    line = line.strip()
                    if (line and 
                        (line[0].isdigit() or line.startswith('-') or line.startswith('•')) and
                        len(line) > 10 and
                        not any(field in line.upper() for field in field_keywords)):
                        bullet_text = line
                        while bullet_text and (bullet_text[0].isdigit() or bullet_text[0] in '-•. '):
                            bullet_text = bullet_text[1:].lstrip()
                        if bullet_text:
                            fallback_bullets.append(bullet_text)
                
                if fallback_bullets:
                    optimized_bullets = fallback_bullets
            
            # If still no bullets found, use original
            if not optimized_bullets or len(optimized_bullets) == 0:
                warnings.append("Could not parse optimized bullets from response")
                optimized_bullets = original_bullets
            
            # If no reasoning found, create a basic one
            if reasoning == "Unable to parse response":
                reasoning = f"Optimized bullets based on {len(standard_search_terms)} standard and {len(high_priority_search_terms)} high-priority search terms"
            
            processing_time = time.time() - start_time
            
            return BulletsOptimizationResult(
                original_bullets=original_bullets,
                optimized_bullets=optimized_bullets,
                standard_search_terms=standard_search_terms,
                high_priority_search_terms=high_priority_search_terms,
                confidence_score=confidence_score,
                optimization_reasoning=reasoning,
                keywords_used=keywords_used,
                changes_made=changes_made,
                preservation_score=preservation_score,
                warnings=warnings,
                processing_time=processing_time,
                model_used=self.llm_client.model_name
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing LLM response: {e}")
            # Return a fallback result
            return BulletsOptimizationResult(
                original_bullets=original_bullets,
                optimized_bullets=original_bullets,
                standard_search_terms=standard_search_terms,
                high_priority_search_terms=high_priority_search_terms,
                confidence_score=0.0,
                optimization_reasoning=f"Error parsing response: {str(e)}",
                keywords_used=[],
                changes_made=[],
                preservation_score=0,
                warnings=[f"Parsing error: {str(e)}"],
                processing_time=time.time() - start_time,
                model_used=self.llm_client.model_name
            )
    
    def get_optimizer_info(self) -> Dict[str, Any]:
        """Get information about the optimizer"""
        return {
            'llm_info': self.llm_client.get_model_info(),
            'prompt_loaded': bool(self.bullets_optimization_prompt),
            'optimizer_type': 'Amazon Product Bullets Optimizer'
        }

