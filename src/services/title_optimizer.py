# src/services/title_optimizer.py
"""
Title Optimizer for Amazon products
"""

import time
import logging
from typing import List, Dict, Any
from .data_models import ProductData, OptimizationResult
from .llm_client import LLMClient


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

        # Comprehensive Title & Feature Optimization Prompt
        self.feature_refinement_prompt = """
You are an expert Amazon product optimizer specializing in BOTH title and feature optimization. Your mission is to maximize search term integration while preserving the original product's comprehensive information and length.

PRODUCT INFORMATION:
- Product ID: {product_id}
- Current Title: {current_title}
- Brand: {brand}
- Description: {description}
- Product Type: {product_type}
- Manufacturer: {manufacturer}
- Category: {category}
- Current Features: {features}

{search_terms_instruction}

CORE OPTIMIZATION PRINCIPLES:

1. SEARCH TERM INCORPORATION STRATEGY:
   You have THREE options for incorporating search terms:
   
   OPTION A - TITLE OPTIMIZATION ONLY:
   - Add search terms directly to the title
   - Replace generic words in title with specific search terms
   - Keep all original title content and length
   - Leave features unchanged
   
   OPTION B - FEATURE REFINEMENT ONLY:
   - Refine existing features to incorporate search terms
   - Add ONE new feature that includes search terms
   - Keep title mostly unchanged
   
   OPTION C - COMBINED APPROACH:
   - Use both title optimization AND feature refinement
   - Distribute search terms between title and features as appropriate
   
   DECISION CRITERIA:
   - ANALYZE EXISTING FEATURES: Look at the current feature list and assess if it already covers the search terms
   - If search terms fit naturally in title AND features are already comprehensive → use OPTION A
   - If search terms are better suited for features OR existing features lack search term coverage → use OPTION B  
   - If you can effectively use both title and features → use OPTION C
   - Always explain your choice in the REASONING field, specifically referencing the existing features

2. TITLE OPTIMIZATION RULES (when chosen):
   - PRESERVE LENGTH: Keep within 10% of original length (prefer longer)
   - ADDITIVE APPROACH: Add search terms without removing important information
   - ENHANCEMENT METHOD: Replace generic words with specific search terms
   - STRUCTURE MAINTENANCE: Keep original title's flow and organization
   - SPECIFICATION PRESERVATION: Never remove quantities, measurements, or technical details

3. FEATURE REFINEMENT RULES (when chosen):
   - REFINE EXISTING: Modify existing features to incorporate search terms naturally
   - ADD NEW FEATURE: Add ONE new feature that includes target search terms
   - PRESERVE ORIGINAL: Keep all original features unless refining them
   - SEARCH-OPTIMIZED: Ensure search terms are naturally incorporated
   - FORMAT CONSISTENCY: Match the style and format of existing features

4. LENGTH PRESERVATION RULES:
   - Original < 150 chars → Optimized should be 150-200 chars
   - Original 150-200 chars → Optimized should be 200-250 chars  
   - Original > 200 chars → Optimized should be within 10% of original length
   - NEVER make the title significantly shorter than the original

5. CONTENT PRESERVATION REQUIREMENTS:
   - Keep 95%+ of original title content
   - Maintain all specifications, quantities, and technical details
   - Preserve brand names, model numbers, and key identifiers
   - Keep all important product descriptors and features
   - Maintain the original title's professional tone and structure

OPTIMIZATION EXAMPLES:

GOOD TITLE OPTIMIZATION:
Original: "Super Ninja Fruit Fly Traps for Indoors - 2 Traps - Highly Effective Eco-Friendly Fruit Fly Catcher for Indoors - Pet and Child Safe - Up to 3 Weeks per Bottle"
Search Terms: "gnat killer indoor spray"
Optimized: "Super Ninja Fruit Fly Traps for Indoors - 2 Traps - Highly Effective Gnat Killer Indoor Spray - Eco-Friendly Fruit Fly Catcher for Indoors - Pet and Child Safe - Up to 3 Weeks per Bottle"
✅ Added search terms while preserving all original content

BAD TITLE OPTIMIZATION:
Original: "Super Ninja Fruit Fly Traps for Indoors - 2 Traps - Highly Effective Eco-Friendly Fruit Fly Catcher for Indoors - Pet and Child Safe - Up to 3 Weeks per Bottle"
Search Terms: "gnat killer indoor spray"
Bad: "Gnat Killer Indoor Spray - Fruit Fly Traps - 2 Traps - Eco-Friendly"
❌ Removed too much important information

FEATURE OPTIMIZATION EXAMPLE:
Original Features: "T8 LED Bulbs 4 Foot, Tube Single Sided Ballast Bypass Type B; BRIGHT AS DAY: Swap your old fluorescent tubes..."
Search Terms: "energy efficient LED lighting"
New Feature: "ENERGY EFFICIENT LED LIGHTING: Reduces electricity costs by up to 60% compared to traditional fluorescent tubes while providing superior brightness and longevity"

REASONING EXAMPLES:

GOOD REASONING (OPTION A - Title Only):
"I chose OPTION A (title optimization only) because the search terms 'energy efficient LED lighting' fit naturally into the existing title structure. The current features already cover brightness and technical specifications well, so adding search terms to the title was more effective than modifying the comprehensive feature list."

GOOD REASONING (OPTION B - Features Only):
"I chose OPTION B (feature refinement only) because the search terms 'commercial grade durability' are better suited for the features section. The existing features focus on brightness and installation, so adding a new feature about durability and commercial use complements the existing feature list without cluttering the title."

GOOD REASONING (OPTION C - Combined):
"I chose OPTION C (combined approach) because 'energy efficient' works well in the title, while 'LED lighting' is better suited for a new feature. I added 'ENERGY EFFICIENT' to the title and created a new feature 'ENERGY EFFICIENT LED LIGHTING: Reduces electricity costs by 60%' to cover both aspects comprehensively."

RESPONSE FORMAT:
You MUST respond in this exact format:

OPTIMIZED_TITLE: [Your optimized title here]
REFINED_FEATURES: [If you chose OPTION A: "No changes to features" | If you chose OPTION B or C: Original features + refined/new features]
CONFIDENCE: [Score from 0.0 to 1.0]
REASONING: [Explain your optimization strategy - which option you chose (A, B, or C) and why. MUST include: 1) Why you chose to modify/not modify the features, 2) How the existing features influenced your decision, 3) Specific details about what you changed in features (if any)]
PRESERVATION_SCORE: [Percentage of original content preserved, 0-100]
KEYWORDS_USED: [List of keywords you incorporated in title and features]
CHANGES_MADE: [Specific changes made to title and features]
WARNINGS: [Any concerns or "None"]

IMPORTANT: 
- If you chose OPTION A (title only): REFINED_FEATURES should be "No changes to features"
- If you chose OPTION B (features only): REFINED_FEATURES should contain refined original features + one new feature
- If you chose OPTION C (combined): REFINED_FEATURES should contain all original features + one new feature
- Always explain in REASONING which option you chose and why

SUCCESS CRITERIA:
- Title length within 10% of original (prefer longer)
- 95%+ content preservation
- All search terms naturally incorporated
- One relevant new feature added
- Original specifications maintained
- Professional, Amazon-ready format

Now optimize the title and refine the features while maximizing search term integration and content preservation:
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
    def optimize_title(self, product_data: ProductData, target_search_terms: List[str], feature_refinement_mode: bool = False) -> OptimizationResult:
        """Optimize product title for target search terms"""
        start_time = time.time()
        
        try:
            # Check if features exist for feature refinement mode
            has_features = product_data.features and len(product_data.features) > 0 and any(feature.strip() for feature in product_data.features if isinstance(feature, str))
            
            # If feature refinement mode is requested but no features exist, fall back to title-only mode
            if feature_refinement_mode and not has_features:
                self.logger.info("Feature refinement mode requested but no features available, falling back to title-only optimization")
                feature_refinement_mode = False
            
            # Prepare the prompt based on mode
            prompt = self._prepare_prompt(product_data, target_search_terms, feature_refinement_mode)
            
            # Get LLM response
            search_terms_str = ", ".join(target_search_terms)
            mode_str = "with feature refinement" if feature_refinement_mode else "title only"
            self.logger.info(f"Optimizing title for product {product_data.product_id} with search terms: {search_terms_str} ({mode_str})")
            response = self.llm_client.generate_response(prompt)
            
            # Log the response for debugging
            self.logger.info(f"LLM Response received: {response[:200]}...")
            if feature_refinement_mode:
                self.logger.info(f"Full LLM Response for feature refinement: {response}")
            
            # Parse the response
            result = self._parse_response(response, product_data, target_search_terms, start_time, feature_refinement_mode)
            
            # Log parsing results for debugging
            if feature_refinement_mode:
                self.logger.info(f"Parsed refined features: {result.refined_features}")
                self.logger.info(f"Feature refinement mode in result: {result.feature_refinement_mode}")
            
            self.logger.info(f"Title optimization completed for product {product_data.product_id}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error optimizing title: {e}")
            raise
    
    def _prepare_prompt(self, product_data: ProductData, target_search_terms: List[str], feature_refinement_mode: bool = False) -> str:
        """Prepare the optimization prompt"""
        # Convert features list to string
        if product_data.features:
            if isinstance(product_data.features, list):
                features_str = ", ".join(product_data.features)
            else:
                # If features is already a string, use it directly
                features_str = str(product_data.features)
        else:
            features_str = "None"
        
        # Format search terms for the prompt
        if len(target_search_terms) == 1:
            search_terms_display = target_search_terms[0]
            search_terms_instruction = f"TARGET SEARCH TERM: {target_search_terms[0]}"
        else:
            search_terms_display = ", ".join(target_search_terms)
            search_terms_instruction = f"TARGET SEARCH TERMS: {', '.join(target_search_terms)}\n\nIMPORTANT: You must incorporate ALL of these search terms naturally into the optimized title. Prioritize the most important/relevant terms but try to include as many as possible."
        
        # Choose the appropriate prompt template
        if feature_refinement_mode:
            prompt_template = self.feature_refinement_prompt
        else:
            prompt_template = self.optimization_prompt
        
        return prompt_template.format(
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
    
    def _parse_response(self, response: str, product_data: ProductData, target_search_terms: List[str], start_time: float, feature_refinement_mode: bool = False) -> OptimizationResult:
        """Parse LLM response into OptimizationResult"""
        try:
            lines = response.strip().split('\n')
            
            # Initialize with defaults
            optimized_title = product_data.current_title
            confidence_score = 0.5
            reasoning = "Unable to parse response"
            keywords_used = []
            warnings = []
            preservation_score = 0
            changes_made = []
            refined_features = None
            
            # Handle features properly for display
            if product_data.features:
                if isinstance(product_data.features, list):
                    original_features = ", ".join(product_data.features)
                else:
                    original_features = str(product_data.features)
            else:
                original_features = None
            
            # Parse each line with more flexible matching - handle multi-line fields
            i = 0
            field_keywords = ['OPTIMIZED_TITLE', 'CONFIDENCE', 'REASONING', 'PRESERVATION_SCORE', 
                            'KEYWORDS_USED', 'CHANGES_MADE', 'WARNINGS', 'REFINED_FEATURES']
            
            while i < len(lines):
                line = lines[i].strip()
                
                # More flexible parsing - handle variations in format
                if 'OPTIMIZED_TITLE' in line and ':' in line:
                    # Capture multi-line optimized title
                    title_parts = [line.split(':', 1)[1].strip()]
                    i += 1
                    # Continue capturing until we hit the next field or end
                    while i < len(lines):
                        next_line = lines[i].strip()
                        # Check if this is the start of a new field
                        if next_line and any(field + ':' in next_line.upper() for field in field_keywords):
                            break
                        if next_line:  # Include non-empty lines
                            title_parts.append(next_line)
                        i += 1
                    optimized_title = ' '.join(title_parts).strip()
                    # Remove markdown artifacts
                    optimized_title = optimized_title.replace('**', '').replace('***', '').strip()
                    continue  # Don't increment i again
                    
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
                    # Continue capturing until we hit the next field or end
                    while i < len(lines):
                        next_line = lines[i].strip()
                        # Check if this is the start of a new field
                        if next_line and any(field + ':' in next_line.upper() for field in field_keywords):
                            break
                        if next_line:  # Include non-empty lines
                            reasoning_parts.append(next_line)
                        i += 1
                    reasoning = ' '.join(reasoning_parts).strip()
                    # Remove markdown artifacts
                    reasoning = reasoning.replace('**', '').replace('***', '').strip()
                    continue  # Don't increment i again since the while loop already did
                    
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
                    # Continue capturing until we hit the next field or end
                    while i < len(lines):
                        next_line = lines[i].strip()
                        # Check if this is the start of a new field
                        if next_line and any(field + ':' in next_line.upper() for field in field_keywords):
                            break
                        if next_line:  # Include non-empty lines
                            keywords_parts.append(next_line)
                        i += 1
                    keywords_str = ' '.join(keywords_parts).strip()
                    keywords_used = [kw.strip() for kw in keywords_str.split(',') if kw.strip()]
                    continue  # Don't increment i again
                    
                elif 'CHANGES_MADE' in line and ':' in line:
                    # Capture multi-line changes
                    changes_parts = [line.split(':', 1)[1].strip()]
                    i += 1
                    # Continue capturing until we hit the next field or end
                    while i < len(lines):
                        next_line = lines[i].strip()
                        # Check if this is the start of a new field
                        if next_line and any(field + ':' in next_line.upper() for field in field_keywords):
                            break
                        if next_line:  # Include non-empty lines
                            changes_parts.append(next_line)
                        i += 1
                    changes_str = ' '.join(changes_parts).strip()
                    changes_made = [c.strip() for c in changes_str.split(',') if c.strip()]
                    continue  # Don't increment i again
                    
                elif 'WARNINGS' in line and ':' in line:
                    # Capture multi-line warnings
                    warnings_parts = [line.split(':', 1)[1].strip()]
                    i += 1
                    # Continue capturing until we hit the next field or end
                    while i < len(lines):
                        next_line = lines[i].strip()
                        # Check if this is the start of a new field
                        if next_line and any(field + ':' in next_line.upper() for field in field_keywords):
                            break
                        if next_line:  # Include non-empty lines
                            warnings_parts.append(next_line)
                        i += 1
                    warnings_str = ' '.join(warnings_parts).strip()
                    if warnings_str.lower() not in ['none', 'n/a', '']:
                        warnings = [w.strip() for w in warnings_str.split(',') if w.strip()]
                    else:
                        warnings = []
                    continue  # Don't increment i again
                    
                elif 'REFINED_FEATURES' in line and ':' in line:
                    # Capture multi-line refined features
                    refined_parts = [line.split(':', 1)[1].strip()]
                    i += 1
                    # Continue capturing until we hit the next field or end
                    while i < len(lines):
                        next_line = lines[i].strip()
                        # Check if this is the start of a new field
                        if next_line and any(field + ':' in next_line.upper() for field in field_keywords):
                            break
                        if next_line:  # Include non-empty lines
                            refined_parts.append(next_line)
                        i += 1
                    refined_features = '\n'.join(refined_parts).strip()
                    # Remove markdown artifacts
                    refined_features = refined_features.replace('**', '').replace('***', '').strip()
                    self.logger.info(f"Found REFINED_FEATURES: {refined_features[:100]}...")
                    continue  # Don't increment i again
                    
                else:
                    i += 1
            
            # If we couldn't parse anything meaningful, try to extract title from the response
            if optimized_title == product_data.current_title and len(response.strip()) > 50:
                # Look for the first line that looks like a title (longer than 20 chars, not a field name)
                for line in lines:
                    line = line.strip()
                    if (len(line) > 20 and 
                        not any(field in line.upper() for field in ['OPTIMIZED_TITLE', 'CONFIDENCE', 'REASONING', 'PRESERVATION', 'KEYWORDS', 'CHANGES', 'WARNINGS', 'REFINED'])):
                        optimized_title = line
                        break
            
            # If still no title found, use the original
            if optimized_title == product_data.current_title:
                warnings.append("Could not parse optimized title from response")
            
            # If no reasoning found, create a basic one
            if reasoning == "Unable to parse response":
                reasoning = f"Optimized title based on search terms: {', '.join(target_search_terms)}"
            
            # If no refined features found but we're in feature refinement mode, try to find them
            if feature_refinement_mode and not refined_features and original_features:
                # Look for any line that might contain refined features
                for line in lines:
                    line = line.strip()
                    if (len(line) > 50 and 
                        ('feature' in line.lower() or 'benefit' in line.lower() or 'advantage' in line.lower()) and
                        not any(field in line.upper() for field in ['OPTIMIZED_TITLE', 'CONFIDENCE', 'REASONING', 'PRESERVATION', 'KEYWORDS', 'CHANGES', 'WARNINGS'])):
                        refined_features = line
                        self.logger.info(f"Found potential refined features in fallback: {refined_features[:100]}...")
                        break
            
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
                model_used=self.llm_client.model_name,
                original_features=original_features,
                refined_features=refined_features,
                feature_refinement_mode=feature_refinement_mode
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
                model_used=self.llm_client.model_name,
                original_features=original_features,
                refined_features=None,
                feature_refinement_mode=feature_refinement_mode
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
