
import simpy

from app.simulation.components.base import SimulatedComponent
from app.simulation.state import ComponentConfig


class DatabaseComponent(SimulatedComponent):
    def __init__(
        self,
        env: simpy.Environment,
        node_id: str,
        config: ComponentConfig,
        pool_size: int = 10,
    ):
        if pool_size < 1:
            raise ValueError("pool_size must be positive")

        super().__init__(env, node_id, config)

        # Database concurrency is bounded by pool size.
        self.resource = simpy.Resource(
            env,
            capacity=pool_size,
        )

        self.pool_size = pool_size
