from enum import Enum


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 5.0):
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be positive")
        if recovery_timeout <= 0:
            raise ValueError("recovery_timeout must be positive")
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.opened_at: float | None = None
        self.probe_in_flight = False
        self.rejected = 0
        self.open_count = 0

    def allow_request(self, now: float) -> bool:
        if self.state == CircuitState.OPEN:
            if self.opened_at is not None and now - self.opened_at >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
            else:
                self.rejected += 1
                return False
        if self.state == CircuitState.HALF_OPEN:
            if self.probe_in_flight:
                self.rejected += 1
                return False
            self.probe_in_flight = True
        return True

    def record_failure(self, now: float):
        self.consecutive_failures += 1
        if self.state == CircuitState.HALF_OPEN or (
            self.state == CircuitState.CLOSED
            and self.consecutive_failures >= self.failure_threshold
        ):
            self.state = CircuitState.OPEN
            self.opened_at = now
            self.open_count += 1
            self.probe_in_flight = False

    def record_success(self):
        # A late completion must not close a circuit that is still open.
        if self.state == CircuitState.OPEN:
            return
        self.consecutive_failures = 0
        self.state = CircuitState.CLOSED
        self.opened_at = None
        self.probe_in_flight = False
