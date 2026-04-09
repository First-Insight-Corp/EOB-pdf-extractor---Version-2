"""
Test script to verify cost calculation functionality
"""

import json
from cost_calculator import CostCalculator, get_cost_breakdown
from cost_config import calculate_token_cost, get_model_pricing, get_model_base_name

def test_single_model_cost():
    """Test cost calculation for a single model"""
    print("=" * 60)
    print("TEST 1: Single Model Cost Calculation")
    print("=" * 60)
    
    # Claude Sonnet - 10k input tokens, 2k output tokens
    model = "claude-sonnet-4"
    input_tokens = 10000
    output_tokens = 2000
    
    cost = calculate_token_cost(input_tokens, output_tokens, model)
    print(f"Model: {model}")
    print(f"Input Tokens: {input_tokens:,}")
    print(f"Output Tokens: {output_tokens:,}")
    print(f"Total Cost: ${cost:.4f}")
    assert cost > 0, "Cost should be greater than 0"
    print("✓ PASSED\n")


def test_model_pricing_lookup():
    """Test pricing lookup for various models"""
    print("=" * 60)
    print("TEST 2: Model Pricing Lookup")
    print("=" * 60)
    
    models = [
        "claude-sonnet-4",
        "claude-sonnet-4-20250514",
        "gemini-2.5-pro",
        "gpt-4o",
        "unknown-model-xyz"  # Should use default
    ]
    
    for model in models:
        normalized = get_model_base_name(model)
        pricing = get_model_pricing(normalized)
        print(f"{model:30} → {normalized:25} → Input: ${pricing['input']:.6f}/1k, Output: ${pricing['output']:.6f}/1k")
    
    print("✓ PASSED\n")


def test_cost_breakdown_from_tokens():
    """Test cost breakdown calculation from complete token structure"""
    print("=" * 60)
    print("TEST 3: Cost Breakdown from Token Structure")
    print("=" * 60)
    
    token_breakdown = {
        "total": {
            "input": 28073,
            "output": 4175
        },
        "by_role": {
            "extractor": {
                "claude-sonnet-4-6": {
                    "input": 18980,
                    "output": 4155
                }
            },
            "auditor": {
                "gemini-2.5-pro": {
                    "input": 9093,
                    "output": 20
                }
            },
            "critic": {}
        }
    }
    
    cost_breakdown = get_cost_breakdown(token_breakdown)
    
    print("Token Breakdown:")
    print(f"  Total - Input: {token_breakdown['total']['input']:,}, Output: {token_breakdown['total']['output']:,}")
    print(f"\nCost Breakdown:")
    print(f"  Total Cost: ${cost_breakdown['total']:.4f}")
    print(f"  Currency: {cost_breakdown['currency']}")
    print(f"\nBy Role:")
    for role, data in cost_breakdown.get('by_role', {}).items():
        print(f"  {role}: ${data.get('total', 0):.4f}")
        for model, model_data in data.get('models', {}).items():
            print(f"    - {model}: ${model_data['cost']:.4f}")
    
    print(f"\nBy Model:")
    for model, cost in cost_breakdown.get('by_model', {}).items():
        print(f"  {model}: ${cost:.4f}")
    
    assert cost_breakdown['total'] > 0, "Total cost should be greater than 0"
    print("\n✓ PASSED\n")


def test_cost_summary():
    """Test cost summary generation"""
    print("=" * 60)
    print("TEST 4: Cost Summary Generation")
    print("=" * 60)
    
    token_breakdown = {
        "total": {
            "input": 28073,
            "output": 4175
        },
        "by_role": {
            "extractor": {
                "claude-sonnet-4-6": {
                    "input": 18980,
                    "output": 4155
                }
            },
            "auditor": {
                "gemini-2.5-pro": {
                    "input": 9093,
                    "output": 20
                }
            },
            "critic": {}
        }
    }
    
    cost_breakdown = get_cost_breakdown(token_breakdown)
    summary = CostCalculator.get_cost_summary(cost_breakdown)
    
    print(summary)
    print("✓ PASSED\n")


def test_edge_cases():
    """Test edge cases"""
    print("=" * 60)
    print("TEST 5: Edge Cases")
    print("=" * 60)
    
    # Empty breakdown
    empty_breakdown = {}
    cost = get_cost_breakdown(empty_breakdown)
    assert cost['total'] == 0, "Empty breakdown should have 0 cost"
    print("✓ Empty breakdown handled correctly")
    
    # None values
    none_breakdown = {
        "total": {"input": 0, "output": 0},
        "by_role": {}
    }
    cost = get_cost_breakdown(none_breakdown)
    assert cost['total'] == 0, "Zero token breakdown should have 0 cost"
    print("✓ Zero token breakdown handled correctly")
    
    # Large token counts
    large_breakdown = {
        "total": {"input": 1000000, "output": 500000},
        "by_role": {
            "extractor": {
                "claude-sonnet-4": {"input": 1000000, "output": 500000}
            },
            "auditor": {},
            "critic": {}
        }
    }
    cost = get_cost_breakdown(large_breakdown)
    print(f"✓ Large token breakdown: ${cost['total']:.4f}")
    
    print("\n✓ PASSED\n")


def main():
    print("\n" + "=" * 60)
    print("COST CALCULATOR TEST SUITE")
    print("=" * 60 + "\n")
    
    try:
        test_single_model_cost()
        test_model_pricing_lookup()
        test_cost_breakdown_from_tokens()
        test_cost_summary()
        test_edge_cases()
        
        print("=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60 + "\n")
        return True
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
