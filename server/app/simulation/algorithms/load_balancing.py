
import random


class LoadBalancer:
    def __init__(
        self,
        algorithm: str = "round_robin",
        seed: int = 42,
    ):
        self.algorithm = algorithm
        self.index = 0
        self.random = random.Random(seed)

    def select(
        self,
        targets: list[str],
        active_counts: dict[str, int] | None = None,
    ) -> str:
        if not targets:
            raise ValueError("No load balancer targets")

        if self.algorithm == "round_robin":
            target = targets[self.index % len(targets)]
            self.index += 1
            return target

        if self.algorithm == "random":
            return self.random.choice(targets)

        if self.algorithm == "least_connections":
            if active_counts is None:
                raise ValueError(
                    "Active counts required for least_connections"
                )

            return min(
                targets,
                key=lambda target: (
                    active_counts.get(target, 0),
                    target,
                ),
            )

        raise ValueError(
            f"Unsupported load balancing algorithm: {self.algorithm}"
        )
