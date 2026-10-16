def calculate_throughput(completed: int, duration_seconds: float) -> float:
    return completed / duration_seconds if duration_seconds > 0 else 0.0


def calculate_error_rate(failed: int, generated: int) -> float:
    return failed / generated if generated > 0 else 0.0
