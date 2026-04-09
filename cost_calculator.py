"""
Cost calculator utility for tracking and computing LLM processing costs.
Handles per-model and per-role cost breakdowns.
"""

import logging
from typing import Dict, Any, Tuple
from cost_config import calculate_token_cost, get_model_base_name, get_model_pricing

logger = logging.getLogger(__name__)


class CostCalculator:
    """Calculate and aggregate costs across models and roles."""
    
    @staticmethod
    def calculate_from_token_breakdown(token_breakdown: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate total cost from token breakdown structure.
        
        Expected structure:
        {
            "total": {"input": X, "output": Y},
            "by_role": {
                "extractor": {"model_name": {"input": X, "output": Y}},
                "auditor": {"model_name": {"input": X, "output": Y}},
                "critic": {"model_name": {"input": X, "output": Y}}
            }
        }
        
        Args:
            token_breakdown: Token usage breakdown by role and model
            
        Returns:
            Cost breakdown dictionary with total and per-role costs
        """
        cost_breakdown = {
            "total": 0.0,
            "currency": "USD",
            "by_role": {},
            "by_model": {}
        }
        
        if not token_breakdown:
            logger.warning("Empty token breakdown provided")
            return cost_breakdown
        
        try:
            by_role = token_breakdown.get("by_role", {})
            
            # Process each role (extractor, auditor, critic)
            for role, models_data in by_role.items():
                if not models_data:
                    continue
                    
                role_cost = 0.0
                role_model_costs = {}
                
                # Process each model in the role
                for model_name, token_counts in models_data.items():
                    if not token_counts or not isinstance(token_counts, dict):
                        continue
                    
                    input_tokens = token_counts.get("input", 0) or 0
                    output_tokens = token_counts.get("output", 0) or 0
                    
                    # Get normalized model name for pricing
                    normalized_model = get_model_base_name(model_name)
                    
                    # Calculate cost for this model
                    model_cost = calculate_token_cost(
                        input_tokens,
                        output_tokens,
                        normalized_model
                    )
                    
                    role_cost += model_cost
                    role_model_costs[model_name] = {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "cost": model_cost
                    }
                    
                    # Aggregate by model
                    if normalized_model not in cost_breakdown["by_model"]:
                        cost_breakdown["by_model"][normalized_model] = 0.0
                    cost_breakdown["by_model"][normalized_model] += model_cost
                
                if role_model_costs:
                    cost_breakdown["by_role"][role] = {
                        "total": round(role_cost, 4),
                        "models": role_model_costs
                    }
                    cost_breakdown["total"] += role_cost
            
            # Round total cost
            cost_breakdown["total"] = round(cost_breakdown["total"], 4)
            
            logger.info(f"Calculated total cost: ${cost_breakdown['total']}")
            return cost_breakdown
            
        except Exception as e:
            logger.error(f"Error calculating cost from token breakdown: {e}", exc_info=True)
            return cost_breakdown
    
    @staticmethod
    def calculate_single_model_cost(
        model_name: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """
        Calculate cost for a single model call.
        
        Args:
            model_name: Name of the LLM model
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Cost in USD
        """
        normalized_model = get_model_base_name(model_name)
        return calculate_token_cost(input_tokens, output_tokens, normalized_model)
    
    @staticmethod
    def get_cost_summary(cost_breakdown: Dict[str, Any]) -> str:
        """
        Generate a human-readable cost summary.
        
        Args:
            cost_breakdown: Cost breakdown dictionary
            
        Returns:
            Formatted cost summary string
        """
        total = cost_breakdown.get("total", 0)
        summary = f"Total Cost: ${total:.4f}\n"
        
        by_role = cost_breakdown.get("by_role", {})
        if by_role:
            summary += "By Role:\n"
            for role, data in by_role.items():
                role_cost = data.get("total", 0) if isinstance(data, dict) else 0
                summary += f"  - {role}: ${role_cost:.4f}\n"
        
        by_model = cost_breakdown.get("by_model", {})
        if by_model:
            summary += "By Model:\n"
            for model, cost in by_model.items():
                summary += f"  - {model}: ${cost:.4f}\n"
        
        return summary


# Convenience functions for direct access
def calculate_cost(
    model_name: str,
    input_tokens: int,
    output_tokens: int
) -> float:
    """Direct function to calculate cost. Alias for CostCalculator.calculate_single_model_cost()"""
    return CostCalculator.calculate_single_model_cost(model_name, input_tokens, output_tokens)


def get_cost_breakdown(token_breakdown: Dict[str, Any]) -> Dict[str, Any]:
    """Direct function to get cost breakdown. Alias for CostCalculator.calculate_from_token_breakdown()"""
    return CostCalculator.calculate_from_token_breakdown(token_breakdown)
