#!/usr/bin/env python3
"""
Test script for the Amazon Product Bullets Optimizer
"""

import os
from src.services.llm_client import LLMClient
from src.services.bullets_optimizer import AmazonProductBulletsOptimizer, BulletsOptimizationResult
from src.services.data_models import ProductData

def main():
    # Load API key from environment
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        print("Please set it using: export OPENAI_API_KEY='your-key-here'")
        return
    
    # Initialize LLM client
    llm_client = LLMClient(api_key=api_key, model_name="gpt-3.5-turbo")
    
    # Initialize bullets optimizer
    bullets_optimizer = AmazonProductBulletsOptimizer(llm_client=llm_client)
    
    print("=" * 80)
    print("Amazon Product Bullets Optimizer - Test")
    print("=" * 80)
    
    # Sample product data
    product_data = ProductData(
        product_id="TEST-001",
        current_title="Premium LED Light Bulb",
        brand="TechLight",
        product_type="Lighting",
        description="A premium LED light bulb for home and office use",
        category="Lighting",
        features=[
            "Energy efficient and long lasting",
            "Easy to install with standard socket",
            "Suitable for indoor use",
            "Provides bright daylight white color"
        ]
    )
    
    # Define search terms with high-priority promotion
    standard_terms = ["LED bulb", "lighting solution"]
    high_priority_terms = ["commercial grade", "professional quality"]  # These will be heavily promoted
    
    print("\n--- Original Bullets ---")
    for i, bullet in enumerate(product_data.features, 1):
        print(f"{i}. {bullet}")
    
    print("\n--- Search Terms ---")
    print(f"Standard Terms: {', '.join(standard_terms)}")
    print(f"High Priority Terms (Heavily Promoted): {', '.join(high_priority_terms)}")
    
    print("\n--- Optimizing Bullets... ---")
    
    try:
        # Optimize bullets
        result = bullets_optimizer.optimize_bullets(
            product_data=product_data,
            standard_search_terms=standard_terms,
            high_priority_search_terms=high_priority_terms,
            add_new_bullets=True
        )
        
        print("\n" + "=" * 80)
        print("OPTIMIZATION COMPLETE")
        print("=" * 80)
        
        print("\n--- Optimized Bullets ---")
        for i, bullet in enumerate(result.optimized_bullets, 1):
            print(f"{i}. {bullet}")
        
        print("\n--- Optimization Details ---")
        print(f"Confidence Score: {result.confidence_score:.2f}")
        print(f"Preservation Score: {result.preservation_score:.1f}%")
        print(f"Processing Time: {result.processing_time:.2f}s")
        
        print("\n--- Keywords Used ---")
        print(f"Keywords: {', '.join(result.keywords_used)}")
        
        print("\n--- Reasoning ---")
        print(result.optimization_reasoning)
        
        print("\n--- Changes Made ---")
        for change in result.changes_made:
            print(f"  • {change}")
        
        if result.warnings:
            print("\n--- Warnings ---")
            for warning in result.warnings:
                print(f"  ⚠ {warning}")
        
        # Show comparison
        print("\n" + "=" * 80)
        print("BEFORE vs AFTER COMPARISON")
        print("=" * 80)
        
        max_len = max(len(product_data.features), len(result.optimized_bullets))
        for i in range(max_len):
            print(f"\nBullet {i+1}:")
            if i < len(product_data.features):
                print(f"  BEFORE: {product_data.features[i]}")
            else:
                print(f"  BEFORE: [none]")
            if i < len(result.optimized_bullets):
                print(f"  AFTER:  {result.optimized_bullets[i]}")
            else:
                print(f"  AFTER:  [none]")
        
        print("\n" + "=" * 80)
        print("Test completed successfully!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\nError during optimization: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

