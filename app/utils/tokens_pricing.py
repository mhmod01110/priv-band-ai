PRICING = {
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},      # per 1K tokens
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "gpt-4o": {"input": 0.005, "output": 0.015},
}

def calculate_cost(input_tokens, output_tokens, model="gpt-4"):
    """حساب التكلفة"""
    pricing = PRICING.get(model, PRICING["gpt-4"])
    input_cost = (input_tokens / 1000) * pricing["input"]
    output_cost = (output_tokens / 1000) * pricing["output"]
    return {
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": input_cost + output_cost
    }