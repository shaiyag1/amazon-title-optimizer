# debug_imports.py
# Save this file in your project root (amazon_title_optimizer folder) and run it

import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
print(f"Project root: {project_root}")
print(f"Python path: {sys.path[:3]}")  # Show first 3 paths
print("-" * 50)

# Test imports step by step
print("Testing imports...")

try:
    print("1. Importing LLMClient...")
    from src.services.llm_client import LLMClient
    print("   ✓ LLMClient imported successfully")
    print(f"   LLMClient class: {LLMClient}")
except Exception as e:
    print(f"   ✗ Failed to import LLMClient: {e}")

try:
    print("\n2. Importing TitleOptimizer...")
    from src.services.title_optimizer import TitleOptimizer
    print("   ✓ TitleOptimizer imported successfully")
    print(f"   TitleOptimizer class: {TitleOptimizer}")
except Exception as e:
    print(f"   ✗ Failed to import TitleOptimizer: {e}")

try:
    print("\n3. Importing data_models...")
    from src.services.data_models import ProductData, OptimizationResult
    print("   ✓ Data models imported successfully")
except Exception as e:
    print(f"   ✗ Failed to import data models: {e}")

print("\n" + "-" * 50)
print("Testing instantiation...")

try:
    print("4. Creating LLMClient instance...")
    # This will fail if no API key, but that's okay for import testing
    client = LLMClient(api_key="test_key", model_name="gpt-3.5-turbo")
    print("   ✓ LLMClient instance created")
except Exception as e:
    print(f"   ✗ Failed to create LLMClient: {e}")

print("\nImport diagnostics complete!")