import random


def exponential_backoff(
    attempt: int, base_delay: float = 0.5, max_delay: float = 30.0,
) -> float:
    if attempt < 1:
        raise ValueError("Attempt must be at least 1")
    if base_delay <= 0 or max_delay <= 0:
        raise ValueError("Retry delays must be positive")
    return min(base_delay * (2 ** (attempt - 1)), max_delay)

def backoff_with_jitter(
    attempt: int, rng: random.Random, base_delay: float = 0.5,
    max_delay: float = 30.0, jitter: float = 0.2,
) -> float:
    if not 0 <= jitter <= 1:
        raise ValueError("jitter must be between 0 and 1")
    delay = exponential_backoff(attempt, base_delay, max_delay)
    return delay * rng.uniform(1 - jitter, 1 + jitter)
