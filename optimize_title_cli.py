#!/usr/bin/env python3
"""
Command Line Title Optimizer
Usage: python optimize_title_cli.py "original title" "search_term1" ["search_term2"] ["search_term3"]
"""

import sys
import os
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from services.llm_client import LLMClient
from services.title_optimizer import TitleOptimizer
from services.data_models import ProductData


def main():
    """Main function for command line title optimization"""
    
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Optimize Amazon product titles for better search term matching",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python optimize_title_cli.py "LED Light Bulb 60W" "outdoor lighting"
  python optimize_title_cli.py "Purity Eyeglass Cleaner Kit" "refill" "spray" "lens cleaner"
  python optimize_title_cli.py "Wireless Headphones" "bluetooth" "noise canceling" "over ear"
        """
    )
    
    parser.add_argument(
        "original_title",
        help="The original product title to optimize"
    )
    
    parser.add_argument(
        "search_term1",
        help="Primary search term to optimize for"
    )
    
    parser.add_argument(
        "search_term2",
        nargs="?",
        help="Optional second search term"
    )
    
    parser.add_argument(
        "search_term3",
        nargs="?",
        help="Optional third search term"
    )
    
    parser.add_argument(
        "--mode",
        choices=["preserve", "standard"],
        default="preserve",
        help="Optimization mode: 'preserve' (default) keeps most original content, 'standard' is more aggressive"
    )
    
    parser.add_argument(
        "--model",
        default="gpt-3.5-turbo",
        help="LLM model to use (default: gpt-3.5-turbo)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output including reasoning and metrics"
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Collect search terms
    search_terms = [args.search_term1]
    if args.search_term2:
        search_terms.append(args.search_term2)
    if args.search_term3:
        search_terms.append(args.search_term3)
    
    # Load environment variables
    load_dotenv()
    
    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ Error: OPENAI_API_KEY not found in environment variables")
        print("Please set your OpenAI API key in a .env file or environment variable")
        sys.exit(1)
    
    try:
        # Initialize LLM client
        print("🔧 Initializing LLM client...")
        llm_client = LLMClient(api_key=api_key, model_name=args.model)
        
        # Initialize title optimizer
        print("🚀 Initializing title optimizer...")
        optimizer = TitleOptimizer(llm_client)
        
        # Set optimization mode
        optimizer.set_prompt_mode(args.mode)
        
        # Create product data
        product_data = ProductData(
            product_id="CLI_OPTIMIZATION",
            current_title=args.original_title,
            brand=None,
            description=None,
            product_type=None,
            manufacturer=None,
            category=None,
            features=[]
        )
        
        # Display input information
        print("\n" + "="*80)
        print("📋 OPTIMIZATION INPUT")
        print("="*80)
        print(f"Original Title: {args.original_title}")
        print(f"Search Terms: {', '.join(search_terms)}")
        print(f"Optimization Mode: {args.mode}")
        print(f"LLM Model: {args.model}")
        print(f"Title Length: {len(args.original_title)} characters")
        
        # Run optimization
        print("\n🔍 Optimizing title...")
        result = optimizer.optimize_title(product_data, search_terms)
        
        # Display results
        print("\n" + "="*80)
        print("🎯 OPTIMIZATION RESULTS")
        print("="*80)
        
        print(f"✅ Optimized Title: {result.optimized_title}")
        print(f"📊 Confidence Score: {result.confidence_score:.2f}")
        print(f"⏱️  Processing Time: {result.processing_time:.2f} seconds")
        
        # Calculate length change
        original_len = len(result.original_title)
        optimized_len = len(result.optimized_title)
        length_change = ((optimized_len - original_len) / original_len) * 100
        print(f"📏 Length Change: {length_change:+.1f}% ({original_len} → {optimized_len} chars)")
        
        if args.verbose:
            print("\n" + "-"*80)
            print("📝 DETAILED ANALYSIS")
            print("-"*80)
            print(f"Reasoning: {result.optimization_reasoning}")
            print(f"Keywords Used: {', '.join(result.keywords_used) if result.keywords_used else 'None'}")
            print(f"Warnings: {', '.join(result.warnings) if result.warnings else 'None'}")
            
            # Show preservation metrics if available
            if hasattr(result, 'preservation_score') and result.preservation_score > 0:
                print(f"Content Preserved: {result.preservation_score:.1f}%")
            
            if hasattr(result, 'changes_made') and result.changes_made:
                print(f"Changes Made: {', '.join(result.changes_made)}")
        
        # Show comparison
        print("\n" + "-"*80)
        print("📊 BEFORE vs AFTER COMPARISON")
        print("-"*80)
        print(f"BEFORE: {result.original_title}")
        print(f"AFTER:  {result.optimized_title}")
        
        # Success indicators
        print("\n" + "-"*80)
        print("✅ SUCCESS INDICATORS")
        print("-"*80)
        
        if result.confidence_score >= 0.8:
            print("🟢 High confidence optimization")
        elif result.confidence_score >= 0.6:
            print("🟡 Medium confidence optimization")
        else:
            print("🔴 Low confidence optimization")
        
        if abs(length_change) <= 20:
            print("🟢 Length change within acceptable range (±20%)")
        else:
            print("🟡 Length change exceeds recommended range (±20%)")
        
        if not result.warnings:
            print("🟢 No warnings or concerns")
        else:
            print(f"🟡 {len(result.warnings)} warning(s) - check details above")
        
        print("\n🎉 Optimization completed successfully!")
        
    except KeyboardInterrupt:
        print("\n⏹️  Optimization cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during optimization: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
