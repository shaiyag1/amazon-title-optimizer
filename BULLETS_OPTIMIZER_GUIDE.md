# Amazon Product Bullets Optimizer - User Guide

## Overview

The **AmazonProductBulletsOptimizer** is a specialized optimizer designed to enhance Amazon product bullet points (features) by incorporating search terms with a **priority-based promotion system**. It intelligently distributes search terms across bullets while preserving the original content.

## Key Features

### 1. **Priority-Based Promotion System**
- **High-Priority Search Terms**: Terms that should be heavily promoted and given special emphasis
- **Standard Search Terms**: Terms integrated naturally without special emphasis
- High-priority terms are placed in multiple bullets, at the beginning when possible, with stronger language

### 2. **Flexible Optimization Strategies**
The optimizer can:
- **Refine existing bullets** by adding search terms naturally
- **Add new bullets** (1-2) to enhance search term coverage
- **Combine both approaches** for maximum effectiveness

### 3. **Content Preservation**
- Maintains 80%+ of original bullet content
- Preserves all specifications, quantities, and technical details
- Keeps the professional tone and format
- No false claims or misleading statements

## How Priority Promotion Works

### High-Priority Terms Are:
1. **Placed Prominently**: At the beginning of bullets when possible
2. **Repeated Naturally**: Appear in 2-3 bullets when relevant
3. **Emphasized Strongly**: Use powerful benefit-focused language
4. **More Visible**: Clearly stand out compared to standard terms

### Standard Terms Are:
1. **Integrated Naturally**: Flow with existing content
2. **Distributed Thoughtfully**: Placed where they fit best
3. **Balanced**: Complementary to high-priority terms

## Usage Example

```python
from src.services.bullets_optimizer import AmazonProductBulletsOptimizer
from src.services.llm_client import LLMClient
from src.services.data_models import ProductData

# Initialize LLM client
llm_client = LLMClient(api_key="your-api-key", model_name="gpt-3.5-turbo")

# Initialize bullets optimizer
bullets_optimizer = AmazonProductBulletsOptimizer(llm_client=llm_client)

# Define product data
product_data = ProductData(
    product_id="12345",
    current_title="Premium LED Light Bulb",
    brand="TechLight",
    features=[
        "Energy efficient and long lasting",
        "Easy to install with standard socket",
        "Suitable for indoor use"
    ]
)

# Define search terms
standard_terms = ["LED bulb", "lighting solution"]
high_priority_terms = ["commercial grade", "professional quality"]  # Heavily promoted

# Optimize bullets
result = bullets_optimizer.optimize_bullets(
    product_data=product_data,
    standard_search_terms=standard_terms,
    high_priority_search_terms=high_priority_terms,
    add_new_bullets=True  # Allow adding new bullets
)

# Access results
print("Original bullets:", result.original_bullets)
print("Optimized bullets:", result.optimized_bullets)
print("Confidence:", result.confidence_score)
print("Reasoning:", result.optimization_reasoning)
```

## Expected Behavior

### Example Input/Output

**Input:**
- **Standard Terms**: `["LED bulb", "lighting solution"]`
- **High Priority Terms**: `["commercial grade", "professional quality"]`

**Original Bullets:**
1. Energy efficient and long lasting
2. Easy to install with standard socket
3. Suitable for indoor use

**Output (Optimized Bullets):**
1. **COMMERCIAL-GRADE** energy efficient **PROFESSIONAL QUALITY** LED bulb technology ensures long-lasting performance
2. Easy to install with standard socket - perfect for **commercial-grade lighting solutions**
3. **PROFESSIONAL QUALITY** construction suitable for indoor and commercial applications
4. **COMMERCIAL-GRADE** durability and reliability for demanding lighting environments

**Key Observations:**
- High-priority terms appear in multiple bullets
- Terms placed at the beginning for visibility
- Strong benefit-focused language used
- New bullet added (#4) to enhance coverage
- Original content preserved

## API Reference

### `optimize_bullets()` Method

```python
def optimize_bullets(
    self,
    product_data: ProductData,
    standard_search_terms: List[str],
    high_priority_search_terms: List[str] = None,
    add_new_bullets: bool = True
) -> BulletsOptimizationResult
```

**Parameters:**
- `product_data`: Product information including current bullets/features
- `standard_search_terms`: List of regular search terms to incorporate
- `high_priority_search_terms`: List of terms that should be heavily promoted (default: empty list)
- `add_new_bullets`: Whether to allow adding new bullets (default: True)

**Returns:**
- `BulletsOptimizationResult` object containing optimized bullets and metadata

### `BulletsOptimizationResult` Dataclass

```python
@dataclass
class BulletsOptimizationResult:
    original_bullets: List[str]
    optimized_bullets: List[str]
    standard_search_terms: List[str]
    high_priority_search_terms: List[str]
    confidence_score: float
    optimization_reasoning: str
    keywords_used: List[str]
    changes_made: List[str]
    preservation_score: float
    warnings: List[str]
    processing_time: float
    model_used: str
```

## Testing

Run the test script to see the optimizer in action:

```bash
export OPENAI_API_KEY='your-api-key-here'
python test_bullets_optimizer.py
```

## When to Use

### Use High-Priority Promotion When:
- You have critical search terms that drive conversions
- You want to emphasize specific product attributes
- Certain terms need maximum visibility
- You want to differentiate from competitors

### Use Standard Search Terms When:
- Terms should be integrated naturally
- You want balanced optimization
- Terms are important but not critical
- You prefer subtle integration

## Best Practices

1. **Be Selective**: Don't mark too many terms as high-priority (3-5 max recommended)
2. **Be Strategic**: Choose terms that truly differentiate your product
3. **Review Output**: Always review optimized bullets for accuracy and tone
4. **Balance**: Ensure bullets remain natural and readable
5. **Test**: Compare different priority configurations to find what works best

## Integration with Other Optimizers

This optimizer works alongside:
- `TitleOptimizer`: Optimizes product titles
- `ContentOptimizer`: Optimizes title, features, and description together
- `DescriptionOptimizer`: Optimizes product descriptions

Use in combination for comprehensive Amazon product optimization.

