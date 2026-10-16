import math


def percentile(values: list[float], p: float) -> float:
    if not 0 <= p <= 100:
        raise ValueError("Percentile must be between 0 and 100")
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * p / 100
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def latency_summary(values: list[float]) -> dict:
    return {
        "avg_ms": sum(values) / len(values) if values else 0.0,
        "p50_ms": percentile(values, 50),
        "p95_ms": percentile(values, 95),
        "p99_ms": percentile(values, 99),
        "min_ms": min(values) if values else 0.0,
        "max_ms": max(values) if values else 0.0,
    }
