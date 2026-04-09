"""
Pricing configuration for LLM API calls
Store token pricing for all supported models
"""

# Pricing per 1,000 tokens in USD
# Last updated: April 2026
MODEL_PRICING = {
    # Claude Models (Anthropic)
    "claude-opus-4": {
        "input": 0.015,  # $15 per 1M input tokens
        "output": 0.075,  # $75 per 1M output tokens
    },
    "claude-sonnet-4": {
        "input": 0.003,  # $3 per 1M input tokens
        "output": 0.015,  # $15 per 1M output tokens
    },
    "claude-sonnet-4-6": {
        "input": 0.003,  # $3 per 1M input tokens
        "output": 0.015,  # $15 per 1M output tokens
    },
    "claude-sonnet-4-20250514": {
        "input": 0.003,
        "output": 0.015,
    },
    "claude-3-5-sonnet-20241022": {
        "input": 0.003,
        "output": 0.015,
    },
    "claude-3-opus-20250219": {
        "input": 0.015,
        "output": 0.075,
    },
    # Gemini Models (Google)
    "gemini-2.5-pro": {
        "input": 0.0001875,  # $0.075 per 1M input tokens
        "output": 0.00075,  # $0.30 per 1M output tokens
    },
    "gemini-2.0-flash": {
        "input": 0.0000375,  # $0.015 per 1M input tokens
        "output": 0.00015,  # $0.06 per 1M output tokens
    },
    "gemini-1.5-pro": {
        "input": 0.00125,  # $0.50 per 1M input tokens
        "output": 0.005,  # $2.00 per 1M output tokens
    },
    "gemini-1.5-flash": {
        "input": 0.0000375,  # $0.015 per 1M input tokens
        "output": 0.00015,  # $0.06 per 1M output tokens
    },
    # OpenAI Models
    "gpt-4o": {
        "input": 0.005,  # $5 per 1M input tokens
        "output": 0.015,  # $15 per 1M output tokens
    },
    "gpt-4-turbo": {
        "input": 0.01,  # $10 per 1M input tokens
        "output": 0.03,  # $30 per 1M output tokens
    },
    # Default fallback for unknown models
    "default": {
        "input": 0.001,
        "output": 0.002,
    }
}


def get_model_pricing(model_name: str) -> dict:
    """
    Get pricing for a specific model.
    Falls back to default if model not found.
    
    Args:
        model_name: Name of the LLM model
        
    Returns:
        dict with 'input' and 'output' keys containing cost per 1k tokens
    """
    # Try exact match first
    if model_name in MODEL_PRICING:
        return MODEL_PRICING[model_name]
    
    # Try partial match for model families
    model_lower = model_name.lower()
    
    for key in MODEL_PRICING:
        if key.lower() in model_lower or model_lower in key.lower():
            return MODEL_PRICING[key]
    
    # Return default pricing
    print(f"Warning: Model '{model_name}' not found in pricing config. Using default pricing.")
    return MODEL_PRICING["default"]


def calculate_token_cost(input_tokens: int, output_tokens: int, model_name: str) -> float:
    """
    Calculate cost for token usage.
    
    Args:
        input_tokens: Number of input tokens used
        output_tokens: Number of output tokens generated
        model_name: Name of the LLM model
        
    Returns:
        Total cost in USD (rounded to 4 decimal places)
    """
    pricing = get_model_pricing(model_name)
    
    # Cost per token = (cost per 1k tokens) / 1000
    input_cost = (input_tokens * pricing["input"]) / 1000
    output_cost = (output_tokens * pricing["output"]) / 1000
    
    total_cost = input_cost + output_cost
    
    return round(total_cost, 4)


def get_model_base_name(model_name: str) -> str:
    """
    Extract base model name, handling various naming conventions.
    
    Args:
        model_name: Full model name (e.g., 'claude-sonnet-4-20250514')
        
    Returns:
        Normalized model name for pricing lookup
    """
    if not model_name:
        return "default"
    
    model_lower = model_name.lower().strip()
    
    # Map common variations to standard names
    if "claude-sonnet-4" in model_lower:
        return "claude-sonnet-4"
    elif "claude-opus" in model_lower:
        return "claude-opus-4"
    elif "gemini-2.5" in model_lower:
        return "gemini-2.5-pro"
    elif "gemini-2.0" in model_lower:
        return "gemini-2.0-flash"
    elif "gemini-1.5-pro" in model_lower:
        return "gemini-1.5-pro"
    elif "gemini-1.5" in model_lower:
        return "gemini-1.5-flash"
    elif "gpt-4o" in model_lower:
        return "gpt-4o"
    elif "gpt-4" in model_lower:
        return "gpt-4-turbo"
    
    return model_name
