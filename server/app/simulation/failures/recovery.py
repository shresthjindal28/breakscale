from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryPolicy:
    recovery_delay_seconds: float = 5.0
    failure_threshold: int = 5

    def __post_init__(self):
        if self.recovery_delay_seconds <= 0:
            raise ValueError("Recovery delay must be positive")
        if self.failure_threshold < 1:
            raise ValueError("Failure threshold must be positive")
