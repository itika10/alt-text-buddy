from dataclasses import dataclass
from typing import List, Dict

@dataclass
class TokenUsage:
    """
    Represents token + cost usage for a single LLM call.
    """
    provider: str          # e.g. "openai", "azure-openai"
    model: str             # e.g. "gpt-4o-mini"
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    context: str           # e.g. "pipeline_reasoner", single_reasoner"
    
def cost_from_usage(
    *,
    input_tokens: int,
    output_tokens: int,
    input_price_per_1k: float,
    output_price_per_1k: float,
) -> float:
    """
    Estimate cost given separate input/output prices per 1K tokens.
    Prices should come from env/config so you can keep them up to date.
    """
    cost_input = (input_tokens / 1_000_000.0) * input_price_per_1k
    cost_output = (output_tokens / 1_000_000.0) * output_price_per_1k
    return round(cost_input + cost_output, 6)

def aggregate_cost(usages: List[TokenUsage]) -> float:
    """
    Sum the cost of a list of token usage records.
    """
    return round(sum(u.cost_usd for u in usages), 6)

def aggregate_by_model(usages: List[TokenUsage]) -> Dict[str, float]:
    """
    Aggregate total cost per model (useful for reporting).
    """
    totals: Dict[str, float] = {}
    for u in usages:
        totals[u.model] = totals.get(u.model, 0.0) + u.cost_usd
    return {model: round(cost, 6) for model, cost in totals.items()}